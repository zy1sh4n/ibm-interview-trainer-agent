"""
RAG Engine — pure-Python, no external vector DB needed.
Uses an in-memory keyword index with TF-IDF-like scoring.
Plugs directly into GraniteClient for generation.
"""
import re
import math
import hashlib
from typing import Dict, List, Optional, Tuple
from config.settings import get_settings

cfg = get_settings()

# ------------------------------------------------------------------
# Built-in interview knowledge base (role × type)
# ------------------------------------------------------------------
KNOWLEDGE_BASE = [
    {"id": "se_tech", "role": "software engineer", "type": "technical",
     "content": (
         "Software Engineer technical questions: data structures (arrays, linked lists, trees, "
         "graphs, hash maps), algorithm complexity (Big-O), system design (microservices, REST APIs, "
         "databases, caching, load balancing), OOP (SOLID, design patterns), coding problems: "
         "two-sum, binary search, dynamic programming, BFS/DFS. "
         "Tip: explain your thought process aloud; start brute-force then optimize.")},
    {"id": "se_behav", "role": "software engineer", "type": "behavioral",
     "content": (
         "Software Engineer behavioral questions: Tell me about a challenging bug you debugged. "
         "Describe a time you disagreed with a technical decision. How do you handle tight deadlines? "
         "STAR method: Situation, Task, Action, Result. Emphasize collaboration and ownership.")},
    {"id": "ds_tech", "role": "data scientist", "type": "technical",
     "content": (
         "Data Scientist questions: ML algorithms (regression, decision trees, SVMs, neural nets), "
         "feature engineering, evaluation metrics (accuracy, F1, AUC-ROC), statistics (hypothesis testing, "
         "A/B testing), Python (pandas, scikit-learn, TensorFlow), SQL. Explain bias-variance tradeoff.")},
    {"id": "pm_tech", "role": "product manager", "type": "technical",
     "content": (
         "Product Manager questions: product sense (design for audience), KPIs for new features, "
         "prioritization (RICE, MoSCoW), root cause analysis (DAU dropped 20%), roadmap planning, "
         "stakeholder alignment, Agile/Scrum ceremonies.")},
    {"id": "hr_all", "role": "all", "type": "hr",
     "content": (
         "Universal HR questions: Tell me about yourself (elevator pitch). "
         "Why do you want to work here? (research company values). "
         "Where do you see yourself in 5 years? What is your greatest weakness? "
         "Salary expectations: research market rates. "
         "Questions to ask: team culture, success metrics, growth opportunities.")},
    {"id": "soft_all", "role": "all", "type": "soft_skills",
     "content": (
         "Soft skills assessment: Communication (structure answers, avoid filler words). "
         "Leadership (drive projects without authority). Conflict resolution (focus on solutions). "
         "Adaptability (pivot under pressure). Time management (Kanban, time-blocking). "
         "Emotional intelligence (self-awareness, empathy, active listening).")},
    {"id": "prep_all", "role": "all", "type": "preparation",
     "content": (
         "Interview preparation strategy: 1. Research the company (products, culture, competitors). "
         "2. Map every job requirement to your experience. 3. Practice aloud — record yourself. "
         "4. Mock interviews (Pramp, Interviewing.io). 5. Prepare 8-10 STAR stories. "
         "6. Technical warm-up: solve 2-3 problems daily for 2 weeks. "
         "7. Day-of: good sleep, review notes, arrive early.")},
    {"id": "entry_all", "role": "all", "type": "entry_level",
     "content": (
         "Entry-level prep (0-2 yrs): highlight academic projects, internships, personal projects. "
         "Demonstrate eagerness to learn. Focus on foundational skills. "
         "OK to say: I haven't done that yet, but here's how I'd approach it.")},
    {"id": "senior_all", "role": "all", "type": "senior",
     "content": (
         "Senior-level prep (5+ yrs): demonstrate leadership, strategic thinking, cross-functional impact. "
         "Quantify achievements (reduced latency 40%, led team of 8). System design at scale. "
         "Mentor others. Prepare for ambiguous problem-solving. Deep failure story.")},
    {"id": "devops_tech", "role": "devops", "type": "technical",
     "content": (
         "DevOps/Cloud questions: CI/CD (Jenkins, GitHub Actions), containerization (Docker, Kubernetes), "
         "IaC (Terraform, Ansible), cloud platforms (AWS, Azure, IBM Cloud), "
         "monitoring (Prometheus, Grafana, ELK), IAM, secrets management, incident response.")},
    {"id": "star_method", "role": "all", "type": "technique",
     "content": (
         "STAR method for behavioral answers: Situation (set the scene briefly), "
         "Task (describe your responsibility), Action (explain exactly what YOU did — use 'I' not 'we'), "
         "Result (quantify the outcome). Keep each story under 2 minutes. "
         "Prepare 8-10 STAR stories covering: leadership, failure, conflict, success, teamwork.")},
]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\b[a-z]{3,}\b", text.lower())


def _tf_idf_score(query_tokens: List[str], doc_tokens: List[str]) -> float:
    """Simple TF overlap score (no IDF needed for small corpus)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_set = set(doc_tokens)
    hits = sum(1 for t in query_tokens if t in doc_set)
    return hits / len(query_tokens)


def retrieve(query: str, top_k: Optional[int] = None) -> List[Dict]:
    """Return top-k knowledge entries most relevant to the query."""
    k = top_k or cfg.rag_top_k
    q_tokens = _tokenize(query)
    scored = []
    for doc in KNOWLEDGE_BASE:
        d_tokens = _tokenize(doc["content"])
        score = _tf_idf_score(q_tokens, d_tokens)
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    threshold = cfg.rag_similarity_threshold
    results = [doc for score, doc in scored if score >= threshold]
    if not results:
        results = [doc for _, doc in scored[:3]]  # relax if nothing passes
    return results[:k]


def build_prompt(query: str, docs: List[Dict], user_ctx: Optional[Dict] = None) -> str:
    """Assemble the Granite instruct prompt with retrieved context."""
    ctx_parts = []
    for i, doc in enumerate(docs, 1):
        ctx_parts.append(f"[Context {i} | {doc['role']} | {doc['type']}]\n{doc['content']}")
    context = "\n\n".join(ctx_parts)

    user_line = ""
    if user_ctx:
        user_line = (
            f"Candidate: {user_ctx.get('name', '')} | "
            f"Role: {user_ctx.get('job_role', '')} | "
            f"Level: {user_ctx.get('level', '')}\n"
        )

    return (
        "<|system|>\n"
        "You are an expert Interview Trainer powered by IBM Granite. "
        "Help the candidate prepare for job interviews with tailored questions, "
        "model answers, and improvement tips. Use only the context provided.\n"
        "<|user|>\n"
        f"{user_line}"
        f"Context:\n{context}\n\n"
        f"Request: {query}\n"
        "<|assistant|>"
    )

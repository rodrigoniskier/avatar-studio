#!/usr/bin/env python3
"""UserPromptSubmit: sugere skills conforme palavras-chave (PT/EN) no prompt."""
import json, re, sys
try:
    prompt = json.load(sys.stdin).get("prompt", "")
except Exception:
    sys.exit(0)
if prompt.lstrip().startswith("/"):
    sys.exit(0)
RULES = [
 (r"\b(program\w*|software|sistema|desenvolv\w*|implement\w*|funcionalidade|feature|aplicativo|\bapp\b|\bapi\b|c[oó]dig\w*|develop\w*|build)\b", ["grill-with-docs","tdd","implement"]),
 (r"\b(requisito\w*|especifica\w*|\bspec\b|planej\w*|an[aá]lis\w*|escopo)\b", ["grill-with-docs","to-spec"]),
 (r"\b(ticket\w*|tarefas?|backlog|issues?)\b", ["to-tickets","triage"]),
 (r"\b(bug\w*|erro\w*|falh\w*|quebr\w*|trav\w*|lent[oa]|debug\w*|depur\w*|diagnostic\w*|crash|exception)\b", ["diagnosing-bugs"]),
 (r"\b(testes?|tdd|cobertura)\b", ["tdd"]),
 (r"\b(revis\w*|review|auditar)\b", ["code-review"]),
 (r"\b(pull request|\bpr\b|merge)\b", ["pr"]),
 (r"\b(arquitetura|refator\w*|m[oó]dulo\w*|d[ií]vida t[eé]cnica)\b", ["improve-codebase-architecture","codebase-design"]),
 (r"\b(gloss[aá]rio|dom[ií]nio|adr|terminologia|vocabul[aá]rio)\b", ["domain-modeling"]),
 (r"\b(pesquis\w*|investig\w*|research)\b", ["research"]),
 (r"\b(prot[oó]tip\w*|prototyp\w*)\b", ["prototype"]),
 (r"\b(roadmap|projeto grande|projeto novo|greenfield)\b", ["wayfinder"]),
 (r"\b(retro\w*|li[cç][oõ]es aprendidas)\b", ["retro"]),
 (r"\b(handoff|outra sess[aã]o|continuar depois)\b", ["handoff"]),
 (r"\b(question[aá]rio|stakeholder)\b", ["to-questionnaire"]),
 (r"\b(n[aã]o entendi|explique de novo|simplifique)\b", ["wait-what"]),
 (r"\b(pre-?commit|husky|lint-staged)\b", ["setup-pre-commit"]),
 (r"\b(git (push|reset)|proteger git)\b", ["git-guardrails-claude-code"]),
 (r"\b(ensinar|aprender|tutorial)\b", ["teach"]),
]
hits = []
for pat, skills in RULES:
    if re.search(pat, prompt, re.I):
        for s in skills:
            if s not in hits: hits.append(s)
if not hits:
    sys.exit(0)
msg = ("[skill-router] Palavras-chave detectadas. Skills instaladas potencialmente relevantes: "
       + ", ".join("/"+s for s in hits[:6])
       + ". Avalie e invoque via Skill tool as que se aplicarem (leia o SKILL.md antes de agir). "
       "Para trabalho novo de desenvolvimento, comece por grill-with-docs; não publique specs/tickets "
       "em tracker externo nem faça commit/push sem confirmação do usuário.")
print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":msg}}))

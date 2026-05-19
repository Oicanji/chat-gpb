TOOL_INSTRUCTIONS = """
Ferramentas disponiveis (somente se estiverem habilitadas para esta pergunta):
- consultar_rules(mensagem): regras operacionais (horario, links do campus).
- buscar_documento(consulta, tags opcional): trechos em documentos do catalogo (PPC, etc.).
- search_knowledge(query): material extra do professor (nao PPC).

Regras:
- Use a pergunta completa do usuario na consulta.
- Se o contexto do sistema ja trouxer trechos, responda com base neles.
- Nao invente bibliografia nem disciplinas.
"""

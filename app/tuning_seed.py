from app.knowledge_store import _load_catalog, _now_iso, _save_catalog, ensure_data_dirs
from app.tuning_store import build_tuning_yaml


def _has_tuning() -> bool:
    return any(i.get("type") == "tuning" for i in _load_catalog().get("items", []))


def seed_default_tuning() -> None:
    if _has_tuning():
        return
    ensure_data_dirs()
    now = _now_iso()
    catalog = _load_catalog()
    from app.config import settings

    entries = [
        (
            "stopwords-pt",
            "Stopwords (busca)",
            build_tuning_yaml(
                "stopword",
                priority=10,
                values=[
                    "para", "com", "sem", "sobre", "qual", "quais", "como",
                    "esse", "essa", "este", "esta", "curso", "cst", "superior",
                    "estudo", "estudar", "materiais", "material", "sao", "ser",
                    "uma", "uns", "das", "dos", "nas", "nos", "que", "por",
                    "mais", "meu", "minha",
                ],
            ),
        ),
        (
            "expand-bibliografia",
            "Expandir: bibliografia",
            build_tuning_yaml(
                "expand_tokens",
                priority=20,
                when_any=["bibliografia", "bibliografica", "livro", "referencia"],
                add=["bibliografia", "complementar", "basica"],
            ),
        ),
        (
            "expand-ementa",
            "Expandir: ementa / competencias",
            build_tuning_yaml(
                "expand_tokens",
                priority=21,
                when_any=["ementa", "conteudo", "conhecimento", "habilidade"],
                add=["conhecimentos", "habilidades", "unidade", "curricular"],
            ),
        ),
        (
            "alias-ieu",
            "Alias: IEU / UX",
            build_tuning_yaml(
                "alias",
                priority=30,
                when_any=["ieu", "ux", "ui"],
                add=["interfaces", "experiencia", "usuario"],
            ),
        ),
        (
            "alias-interface",
            "Alias: interface e experiencia",
            build_tuning_yaml(
                "alias",
                priority=31,
                when_any=["interface", "experiencia", "usuario"],
                add=["interfaces", "experiencia", "usuario", "ieu"],
            ),
        ),
        (
            "alias-algoritmos",
            "Alias: algoritmos",
            build_tuning_yaml(
                "alias",
                priority=32,
                when_any=["algoritmo", "programacao"],
                add=["algoritmos", "programacao", "fundamentos"],
            ),
        ),
        (
            "course-tecnico-em",
            "Curso: tecnico em informatica",
            build_tuning_yaml(
                "course_signal",
                priority=40,
                phrase="tecnico em informatica",
                target="tecnico",
                weight=2,
            ),
        ),
        (
            "course-tecnico-integrado",
            "Curso: tecnico integrado",
            build_tuning_yaml(
                "course_signal",
                priority=41,
                phrase="tecnico integrado",
                target="tecnico",
            ),
        ),
        (
            "course-ensino-medio",
            "Curso: ensino medio integrado",
            build_tuning_yaml(
                "course_signal",
                priority=42,
                phrase="ensino medio integrado",
                target="tecnico",
            ),
        ),
        (
            "course-sistemas-internet",
            "Curso: sistemas para internet",
            build_tuning_yaml(
                "course_signal",
                priority=43,
                phrase="sistemas para internet",
                target="sistemas",
                weight=2,
            ),
        ),
        (
            "course-cst",
            "Curso: CST",
            build_tuning_yaml(
                "course_signal",
                priority=44,
                phrase="cst",
                target="sistemas",
                weight=2,
            ),
        ),
        (
            "course-superior",
            "Curso: curso superior",
            build_tuning_yaml(
                "course_signal",
                priority=45,
                phrase="curso superior",
                target="sistemas",
            ),
        ),
        (
            "course-sistemas-weak",
            "Curso (fraco): em sistemas",
            build_tuning_yaml(
                "course_signal",
                priority=46,
                phrase="em sistemas",
                target="sistemas",
            ),
        ),
        (
            "auto-bibliografia",
            "Auto-busca: bibliografia",
            build_tuning_yaml(
                "auto_search",
                priority=50,
                when_any=["bibliografia", "bibliografica"],
            ),
        ),
        (
            "auto-ementa",
            "Auto-busca: ementa",
            build_tuning_yaml(
                "auto_search",
                priority=51,
                when_any=["ementa"],
            ),
        ),
        (
            "auto-competencias",
            "Auto-busca: competencias",
            build_tuning_yaml(
                "auto_search",
                priority=52,
                when_any=["competencia", "competencias", "conhecimentos", "habilidades"],
            ),
        ),
        (
            "auto-disciplina",
            "Auto-busca: disciplina / PPC",
            build_tuning_yaml(
                "auto_search",
                priority=53,
                when_any=[
                    "unidade curricular",
                    "disciplina",
                    "ppc",
                    "carga horaria",
                    "semestre",
                    "fase",
                ],
            ),
        ),
        (
            "auto-materiais",
            "Auto-busca: materiais complementares",
            build_tuning_yaml(
                "auto_search",
                priority=54,
                when_any=["material complementar", "materiais complementares"],
            ),
        ),
        (
            "auto-referencias",
            "Auto-busca: referencias / livros",
            build_tuning_yaml(
                "auto_search",
                priority=55,
                when_any=["referencia", "referencias", "livro", "livros"],
            ),
        ),
        (
            "section-ppc-uc",
            "Secao PPC: Unidade Curricular",
            build_tuning_yaml(
                "section_header",
                priority=60,
                scope_mode="tags",
                scope_tags_any=["ppc"],
                pattern=r"^(?:\(\^\)\s*)?\*\*Unidade Curricular:\*\*\s*(.+?)(?:\s*\*\*CH\*|\s*$)",
            ),
        ),
        (
            "search-matriz-fase",
            "Busca: lista / fase / semestre",
            build_tuning_yaml(
                "search_profile",
                priority=45,
                scope_mode="tags",
                scope_tags_any=["ppc"],
                when_any=[
                    "terceiro semestre",
                    "3ª fase",
                    "3a fase",
                    "todas as materias",
                    "todas as matérias",
                    "matriz curricular",
                    "quais materias",
                    "lista de materias",
                ],
                max_sections=12,
                excerpt="full",
            ),
        ),
        (
            "tool-horario",
            "Tools: horario / campus",
            build_tuning_yaml(
                "tool_policy",
                priority=70,
                when_any=["horario", "grade de aula", "horarios"],
                tools=["consultar_rules"],
            ),
        ),
        (
            "tool-ppc",
            "Tools: PPC / disciplina",
            build_tuning_yaml(
                "tool_policy",
                priority=71,
                when_any=[
                    "bibliografia",
                    "ementa",
                    "disciplina",
                    "ppc",
                    "unidade curricular",
                    "carga horaria",
                ],
                tools=["buscar_documento"],
            ),
        ),
    ]

    for item_id, title, yaml_content in entries:
        rel = f"tuning/{item_id}.yaml"
        path = settings.data_dir / rel
        path.write_text(yaml_content, encoding="utf-8")
        catalog.setdefault("items", []).append(
            {
                "id": item_id,
                "type": "tuning",
                "title": title,
                "triggers": [],
                "tags": [],
                "filename": rel,
                "readonly": True,
                "created_at": now,
                "updated_at": now,
            }
        )

    _save_catalog(catalog)


_EXTRA_KIND_ENTRIES = [
    (
        "expand-semestre-1",
        "Expandir: 1o semestre / 1a fase",
        build_tuning_yaml(
            "expand_tokens",
            priority=22,
            when_any=["primeiro semestre", "1o semestre", "1 semestre", "primeira fase"],
            add=["1a", "fase", "total", "carga", "horaria"],
        ),
    ),
    (
        "expand-semestre-2",
        "Expandir: 2o semestre / 2a fase",
        build_tuning_yaml(
            "expand_tokens",
            priority=23,
            when_any=["segundo semestre", "2o semestre", "2 semestre", "segunda fase"],
            add=["2a", "fase", "total", "carga", "horaria"],
        ),
    ),
    (
        "expand-semestre-3",
        "Expandir: 3o semestre / 3a fase",
        build_tuning_yaml(
            "expand_tokens",
            priority=24,
            when_any=["terceiro semestre", "3o semestre", "3 semestre", "terceira fase"],
            add=["3a", "fase", "total", "carga", "horaria"],
        ),
    ),
    (
        "search-matriz-fase",
        "Busca: lista / fase / semestre",
        build_tuning_yaml(
            "search_profile",
            priority=45,
            scope_mode="tags",
            scope_tags_any=["ppc"],
            when_any=[
                "primeiro semestre",
                "segundo semestre",
                "terceiro semestre",
                "1a fase",
                "2a fase",
                "3a fase",
                "todas as materias",
                "todas as matérias",
                "matriz curricular",
                "quais materias",
                "lista de materias",
            ],
            max_sections=8,
            excerpt="full",
        ),
    ),
    (
        "tool-horario",
        "Tools: horario / campus",
        build_tuning_yaml(
            "tool_policy",
            priority=70,
            when_any=["horario", "grade de aula", "horarios"],
            tools=["consultar_rules"],
        ),
    ),
    (
        "tool-ppc",
        "Tools: PPC / disciplina",
        build_tuning_yaml(
            "tool_policy",
            priority=71,
            when_any=[
                "bibliografia",
                "ementa",
                "disciplina",
                "ppc",
                "unidade curricular",
                "carga horaria",
            ],
            tools=["buscar_documento"],
        ),
    ),
]


def ensure_tuning_extras() -> None:
    if not _has_tuning():
        seed_default_tuning()
        return
    from app.config import settings

    catalog = _load_catalog()
    existing = {i.get("id") for i in catalog.get("items", [])}
    added = False
    now = _now_iso()
    for item_id, title, yaml_content in _EXTRA_KIND_ENTRIES:
        if item_id in existing:
            continue
        rel = f"tuning/{item_id}.yaml"
        path = settings.data_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml_content, encoding="utf-8")
        catalog.setdefault("items", []).append(
            {
                "id": item_id,
                "type": "tuning",
                "title": title,
                "triggers": [],
                "tags": [],
                "filename": rel,
                "readonly": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        added = True
    if added:
        _save_catalog(catalog)
        from app.tuning_store import invalidate_tuning_cache

        invalidate_tuning_cache()

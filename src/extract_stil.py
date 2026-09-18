from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import pdfplumber


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "source"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "config" / "metadata_stil2019.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "corpus_stil2019.json"


REFERENCE_HEADING = re.compile(r"(?im)^\s*(references|bibliography|refer[eê]ncias)\s*$")
ABSTRACT_HEADING = re.compile(r"(?im)^\s*(abstract|resumo)\.?")
KEYWORDS_HEADING = re.compile(r"(?im)^\s*(keywords?|palavras[- ]chave)\s*:\s*")
NOISE_LINE = re.compile(
    r"^(?:\d+|Copyright.*|Use permitted under.*|CEUR-WS\.org/Vol-\d+/.*\.pdf)$",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    """Preserva Unicode, corrigindo apenas espacos e hifens de quebra de linha."""
    text = unicodedata.normalize("NFC", text).replace("\u00a0", " ")
    # Mantem quebras de linha para reconstruir palavras e sentencas; remove
    # apenas caracteres de controle espurios inseridos por algumas fontes PDF.
    text = "".join(
        char for char in text if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(?<=[\w])-\n(?=[a-z])", "", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def page_text(page: pdfplumber.page.Page) -> str:
    """Reconstrui linhas com palavras posicionais, evitando texto colado em PDF."""
    words = page.extract_words(x_tolerance=2, y_tolerance=3, use_text_flow=True)
    usable = [
        word
        for word in words
        # Remove a URL vertical na margem e os rodapes; o miolo permanece intacto.
        if page.width * 0.04 < word["x0"] < page.width * 0.96
        and page.height * 0.055 < word["top"] < page.height * 0.94
    ]
    rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for word in usable:
        rows[round(word["top"] / 3)].append(word)

    lines = []
    for _, row in sorted(rows.items()):
        row.sort(key=lambda item: item["x0"])
        line = " ".join(item["text"] for item in row).strip()
        if line and not NOISE_LINE.match(line):
            lines.append(line)
    return "\n".join(lines)


def extract_pdf_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n\n".join(page_text(page) for page in pdf.pages)


def first_page_layout(pdf_path: Path) -> str:
    """Texto com linhas visuais, mais adequado a metadados da primeira pagina."""
    with pdfplumber.open(pdf_path) as pdf:
        return pdf.pages[0].extract_text(layout=True) or ""


def clean_layout_line(line: str) -> str:
    return normalize(line).replace("¸", "ç").replace("´", "")


def automatic_metadata(pdf_path: Path, base_url: str, publication_date: str) -> dict[str, Any]:
    """Extrai metadados visiveis e marca campos incertos para revisao humana."""
    layout_lines = [clean_layout_line(line) for line in first_page_layout(pdf_path).splitlines()]
    layout_lines = [line for line in layout_lines if line]
    abstract_at = next((i for i, line in enumerate(layout_lines) if re.match(r"^(Abstract|Resumo)\.", line)), len(layout_lines))
    header = layout_lines[:abstract_at]

    # A primeira linha de autoria tem sobrescritos (ex.: Santos1,2) ou ORCID.
    author_start = next(
        (i for i, line in enumerate(header) if re.search(r"[A-Za-zÀ-ÿ]\d+(?:,\d+)?(?:\[|,|$)", line)),
        None,
    )
    title_lines = header[:author_start] if author_start is not None else header[:1]
    title = " ".join(title_lines).rstrip("?*")
    author_lines = header[author_start:] if author_start is not None else []

    affiliation_by_id: dict[str, str] = {}
    for line in author_lines:
        match = re.match(r"^(\d+)\s+(.+?)(?:,?\s*[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})?$", line)
        if match:
            affiliation_by_id[match.group(1)] = match.group(2).rstrip(",")

    author_text = " ".join(
        line for line in author_lines if not re.match(r"^\d+\s+", line) and "@" not in line
    )
    author_text = re.sub(r"\band\s+", "", author_text)
    person_pattern = re.compile(
        r"(?P<name>[A-ZÀ-Ý][A-Za-zÀ-ÿ'’ .-]*?)(?P<ids>\d+(?:,\d+)*)(?:\[(?P<orcid>[\d -Xx]+)\])?(?=,|$)"
    )
    authors = []
    for match in person_pattern.finditer(author_text):
        name = re.sub(r"\s+", " ", match.group("name")).strip(" ,")
        ids = match.group("ids").split(",")
        affiliations = [affiliation_by_id[identifier] for identifier in ids if identifier in affiliation_by_id]
        raw_orcid = match.group("orcid")
        orcid = None
        if raw_orcid:
            digits = re.sub(r"[^\dXx]", "", raw_orcid).upper()
            if len(digits) == 16:
                orcid = "https://orcid.org/" + "-".join((digits[:4], digits[4:8], digits[8:12], digits[12:]))
        authors.append(
            {"nome": name, "afiliacao": " / ".join(affiliations), "orcid": orcid}
        )

    first_page = extract_pdf_text(pdf_path).split("\n\n", 1)[0]
    keyword_match = KEYWORDS_HEADING.search(first_page)
    keywords = []
    if keyword_match:
        keyword_text = first_page[keyword_match.end() :]
        keyword_text = re.split(r"(?m)^\s*1\s+[A-Z]", keyword_text)[0]
        keywords = [item.strip() for item in re.split(r"\s*[·•]\s*", normalize(keyword_text)) if item.strip()]

    return {
        "titulo": title,
        "informacoes_url": f"{base_url.rstrip('/')}/{pdf_path.name}",
        "idioma": "Inglês",
        "storage_key": f"files/{pdf_path.name}",
        "autores": authors,
        "data_publicacao": publication_date,
        "keywords": keywords,
    }


def section_parts(text: str) -> tuple[str, str, list[str]]:
    """Retorna texto processavel, resumo e referencias, nessa ordem."""
    reference_match = REFERENCE_HEADING.search(text)
    article = text[: reference_match.start()] if reference_match else text
    reference_text = text[reference_match.end() :] if reference_match else ""

    abstract_match = ABSTRACT_HEADING.search(article)
    if abstract_match:
        abstract_end = KEYWORDS_HEADING.search(article, abstract_match.end())
        # Se nao houver keywords, a primeira secao numerada encerra o resumo.
        if not abstract_end:
            abstract_end = re.search(r"(?m)^\s*1\s+[A-Z]", article[abstract_match.end() :])
            end = abstract_match.end() + abstract_end.start() if abstract_end else len(article)
        else:
            end = abstract_end.start()
        abstract = normalize(article[abstract_match.end() : end])
        # O trecho anterior ao resumo contem titulo, autoria e afiliacoes. Os
        # metadados ja os armazenam em campos proprios e eles nao devem entrar
        # no processamento linguistico.
        article = article[abstract_match.start() :]
    else:
        abstract = ""

    references = split_references(reference_text)
    return normalize(article), abstract, references


def split_references(reference_text: str) -> list[str]:
    """Une linhas de uma mesma referencia numerada sem perder o conteudo."""
    chunks = re.split(r"(?m)^\s*(?=\d+\.\s)", reference_text.strip())
    return [normalize(chunk) for chunk in chunks if re.match(r"^\d+\.\s", chunk.strip())]


def build_record(pdf_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    raw_text = extract_pdf_text(pdf_path)
    article, abstract, references = section_parts(raw_text)
    record = {
        "titulo": metadata.get("titulo", ""),
        "informacoes_url": metadata.get("informacoes_url", ""),
        "idioma": metadata.get("idioma", ""),
        "storage_key": metadata.get("storage_key", f"files/{pdf_path.name}"),
        "autores": metadata.get("autores", []),
        "data_publicacao": metadata.get("data_publicacao", ""),
        "resumo": abstract or metadata.get("resumo", ""),
        "keywords": metadata.get("keywords", []),
        "referencias": references,
        "artigo_completo": article,
        # Estes tres campos sao preenchidos na segunda etapa, com spaCy.
        "artigo_tokenizado": [],
        "pos_tagger": [],
        "lema": [],
    }
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Extracao estrutural de PDFs do STIL.")
    parser.add_argument("pdfs", nargs="*", type=Path)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--gerar-metadata", action="store_true", help="Gera somente o metadata.")
    parser.add_argument("--regenerar-metadata", action="store_true", help="Substitui metadados existentes.")
    parser.add_argument("--base-url", default="https://ceur-ws.org/Vol-2583")
    parser.add_argument("--data-publicacao", default="26/03/2020")
    args = parser.parse_args()

    pdfs = sorted(args.pdfs) if args.pdfs else sorted(DEFAULT_SOURCE_DIR.glob("*.pdf"))
    pdfs += sorted(DEFAULT_SOURCE_DIR.glob("*.PDF")) if not args.pdfs else []
    if not pdfs:
        parser.error(
            f"Nenhum PDF encontrado em {DEFAULT_SOURCE_DIR}. "
            "Adicione os artigos nessa pasta e execute novamente."
        )

    existing_metadata: dict[str, Any] = {}
    if args.metadata.exists() and not args.regenerar_metadata:
        existing_metadata = json.loads(args.metadata.read_text(encoding="utf-8"))

    generated_metadata = {
        path.name: automatic_metadata(path, args.base_url, args.data_publicacao)
        for path in pdfs
        if args.regenerar_metadata or path.name not in existing_metadata
    }
    metadata = {**existing_metadata, **generated_metadata}
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.gerar_metadata:
        print(f"Metadados de {len(pdfs)} artigos atualizados em {args.metadata}")
        return

    records = [build_record(path, metadata.get(path.name, {})) for path in pdfs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(records)} artigos extraidos em {args.output}")
    for record in records:
        print(f"- {record['titulo']}: {len(record['referencias'])} referencias")


if __name__ == "__main__":
    main()

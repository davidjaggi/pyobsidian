import os
import pandas as pd

# Add a YAML header to a markdown file if not present, using Zotero item metadata

def add_yaml_header(file_path, item, note_title):
    """Add YAML header to the markdown file if not present."""
    try:
        citekey = item["data.citekey"]
        zotero_link = item["data.zotero_link"]
        title = item["data.title"]
        year = item["data.year"]
        abstract = item["data.abstractNote"] if "data.abstractNote" in item else ""
        creator = item["meta.creatorSummary"]

        # Handle year formatting
        if pd.notna(year) and isinstance(year, float):
            year = int(year)

        # Create aliases
        creator_year = f"{creator} ({year})"
        creator_year_alt = f"{creator}, ({year})"

        # Create YAML header
        yaml_header = f"""---\ntitle: \"{title}\"\ncitekey: \"{citekey}\"\nzotero: {zotero_link}\nabstract: \"{abstract}\"\naliases: \n  - {creator_year}\n  - {creator_year_alt}\n  - \"{title}\"\ntags:\n  - paper\n---\n"""

        # Add YAML header to file
        with open(file_path, "r+", encoding="utf-8") as f:
            content = f.read()
            f.seek(0, 0)
            f.write(yaml_header + content)

        print(f"Added YAML header to {note_title}")

    except KeyError as e:
        print(f"Warning: Missing required field {e} for {note_title}. Skipping file.")
        return False
    return True


# Download a PDF from Zotero if not already present in the local directory

def download_pdf_if_needed(item, note_title, pdf_files, df_items, VAULT_PATH, REFERENCES, zot):
    """Download PDF from Zotero if not already present."""
    pdf_file = f"{note_title}.pdf"
    if pdf_file not in pdf_files:
        try:
            parent_key = item["key"]
            pdf_attachments = df_items[
                (df_items["data.parentItem"] == parent_key)
                & (df_items["links.enclosure.type"] == "application/pdf")
            ]

            if not pdf_attachments.empty:
                pdf_key = pdf_attachments.iloc[0]["key"]
                pdf_path = os.path.join(VAULT_PATH, REFERENCES, "pdfs")
                zot.dump(pdf_key, pdf_file, pdf_path)
                print(f"Downloaded PDF for {note_title}")
            else:
                print(f"Warning: No PDF attachment found for {note_title} in Zotero.")
        except Exception as e:
            print(f"Error downloading PDF for {note_title}: {e}")


# Embed a PDF under the # Paper section in a markdown file if not already present

def embed_pdf_section(file_path, note_title):
    """Embed PDF under # Paper section if not present."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if "# Paper" not in content:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n# Paper\n\n![PDF](pdfs/{note_title}.pdf)\n")
        print(f"Embedded PDF for {note_title} under # Paper section.")


# Process all markdown files: add YAML headers, download PDFs, and embed PDF under # Paper

def process_markdown_files(md_files, df_items, pdf_files, VAULT_PATH, REFERENCES, zot):
    """Process markdown files to add YAML headers, download PDFs, and embed PDF under # Paper section."""
    for md_file in md_files:
        print(f"Processing file: {md_file}")
        file_path = os.path.join(VAULT_PATH, REFERENCES, md_file)
        note_title = md_file[:-3]  # Remove .md extension
        with open(file_path, "r", encoding="utf-8") as f:
            first_line = f.readline()
        has_frontmatter = first_line.startswith("---")
        if not has_frontmatter:
            matching_items = df_items[df_items["data.citekey"] == note_title]
            if matching_items.empty:
                print(f"Warning: No matching item found for {note_title}. Skipping file.")
                continue
            item = matching_items.iloc[0]
            if not add_yaml_header(file_path, item, note_title):
                continue
            download_pdf_if_needed(item, note_title, pdf_files, df_items, VAULT_PATH, REFERENCES, zot)
        embed_pdf_section(file_path, note_title)


# Create a Zotero select link for a given row

def create_zotero_link(row):
    """Create a Zotero select link for a given row."""
    return f"zotero://select/items/{row['key']}"


# Extract the citekey from the 'data.extra' field in a row

def create_citekey(row):
    """Extract the citekey from the 'data.extra' field in a row."""
    if row['data.extra'] not in [None, ""]:
        try:
            return f"@{row["data.extra"].split('Citation Key: ')[1].split('\\n')[0]}"
        except:
            pass
    else:
        pass


# Extract the year from the 'data.date' field in a row, handling various date formats

def create_year(row):
    """Extract the year from the 'data.date' field in a row, handling various date formats."""
    if row['data.date'] not in [None, ""]:
        try:
            # Attempt to parse the date
            return int(pd.to_datetime(row['data.date'], errors='coerce').year)
        except ValueError:
            # If parsing fails, return None
            return None

# Literature object to represent a paper/item with citekey as main identifier
class Literature:
    def __init__(self, citekey, title, zotero_link, abstract, aliases, tags):
        self.citekey = citekey
        self.title = title
        self.zotero_link = zotero_link
        self.abstract = abstract
        self.aliases = aliases
        self.tags = tags

    def __repr__(self):
        return f"Literature(citekey={self.citekey}, title={self.title})"

    @classmethod
    def from_item(cls, item):
        """Create a Literature object from a Zotero item (row or dict)."""
        citekey = item.get("data.citekey")
        title = item.get("data.title")
        zotero_link = item.get("data.zotero_link")
        abstract = item.get("data.abstractNote", "")
        aliases = [
            f"{item.get('meta.creatorSummary', '')} ({item.get('data.year', '')})",
            f"{item.get('meta.creatorSummary', '')}, ({item.get('data.year', '')})",
            title
        ]
        tags = ["paper"]
        return cls(citekey, title, zotero_link, abstract, aliases, tags)

    @classmethod
    def from_frontmatter(cls, frontmatter_dict):
        """Create a Literature object from a markdown frontmatter dictionary, supporting nested items as properties."""
        citekey = frontmatter_dict.get("citekey")
        title = frontmatter_dict.get("title")
        zotero_link = frontmatter_dict.get("zotero")
        abstract = frontmatter_dict.get("abstract", "")
        aliases = frontmatter_dict.get("aliases", [])
        tags = frontmatter_dict.get("tags", [])
        # Collect any additional properties (including nested items)
        extra_properties = {}
        for k, v in frontmatter_dict.items():
            if k not in {"citekey", "title", "zotero", "abstract", "aliases", "tags"}:
                extra_properties[k] = v
        obj = cls(citekey, title, zotero_link, abstract, aliases, tags)
        for k, v in extra_properties.items():
            setattr(obj, k, v)
        return obj

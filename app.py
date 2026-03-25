import os
import re
import tempfile
from flask import Flask, render_template, request, jsonify
import pdfplumber

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max


def parse_float(val):
    """Convert string to float, handles French decimal format (comma)."""
    if val is None:
        return None
    val = str(val).strip().replace('\xa0', '').replace(' ', '')
    val = val.replace(',', '.')
    val = re.sub(r'[^\d.\-]', '', val)
    if not val or val == '.':
        return None
    try:
        f = float(val)
        return f if f > 0 else None
    except ValueError:
        return None


def find_column_indices(row):
    """Map column names to their index from a header row."""
    col_map = {}
    for i, cell in enumerate(row):
        if cell is None:
            continue
        cell_upper = str(cell).strip().upper().replace('\n', ' ')
        if cell_upper == 'ARTICLE':
            col_map['article'] = i
        elif 'DÉSIGNATION' in cell_upper or 'DESIGNATION' in cell_upper:
            col_map['designation'] = i
        elif 'PMP' in cell_upper or 'DPA' in cell_upper:
            col_map['pmp_dpa'] = i
        elif 'PA FR' in cell_upper or cell_upper == 'PA FR':
            col_map['pa_fr'] = i
    return col_map


def parse_pmp_pdf(pdf_path):
    """Extract article data from a PMP study PDF."""
    articles = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Try line-based table extraction first (works well for bordered tables)
            for strategy in [
                {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                {"vertical_strategy": "text", "horizontal_strategy": "lines"},
                {"vertical_strategy": "lines", "horizontal_strategy": "text"},
            ]:
                tables = page.extract_tables(strategy)
                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # Find header row containing "Article"
                    header_idx = None
                    col_map = {}
                    for i, row in enumerate(table):
                        if not row:
                            continue
                        col_map = find_column_indices(row)
                        if 'article' in col_map and (
                            'pmp_dpa' in col_map or 'pa_fr' in col_map
                        ):
                            header_idx = i
                            break

                    if header_idx is None:
                        continue

                    # Extract data rows
                    for row in table[header_idx + 1:]:
                        if not row:
                            continue

                        art_col = col_map.get('article')
                        if art_col is None or art_col >= len(row):
                            continue

                        art_val = row[art_col]
                        if not art_val:
                            continue

                        article = str(art_val).strip().replace('*', '').strip()
                        # Article refs are 4-6 digit numbers
                        if not re.match(r'^\d{4,6}$', article):
                            continue

                        designation = ''
                        des_col = col_map.get('designation')
                        if des_col is not None and des_col < len(row):
                            designation = str(row[des_col] or '').strip()
                            # Clean up newlines
                            designation = ' '.join(designation.split())

                        pmp_dpa = None
                        pmp_col = col_map.get('pmp_dpa')
                        if pmp_col is not None and pmp_col < len(row):
                            pmp_dpa = parse_float(row[pmp_col])

                        pa_fr = None
                        pafr_col = col_map.get('pa_fr')
                        if pafr_col is not None and pafr_col < len(row):
                            pa_fr = parse_float(row[pafr_col])

                        if pmp_dpa is None and pa_fr is None:
                            continue

                        # Avoid duplicates
                        if not any(a['article'] == article for a in articles):
                            articles.append({
                                'article': article,
                                'designation': designation,
                                'pmp_dpa': pmp_dpa,
                                'pa_fr': pa_fr,
                            })

                if articles:
                    break  # Found articles with this strategy, move to next page

    return articles


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné.'}), 400

    file = request.files['pdf']
    if not file or file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné.'}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Le fichier doit être au format PDF.'}), 400

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        articles = parse_pmp_pdf(tmp_path)
        if not articles:
            return jsonify({
                'error': (
                    "Aucun article trouvé dans ce PDF. "
                    "Vérifiez qu'il s'agit bien d'une étude devis PMP avec les colonnes "
                    "Article, PMP/DPA et PA FR."
                )
            }), 422
        return jsonify({'articles': articles, 'count': len(articles)})
    except Exception as e:
        return jsonify({'error': f'Erreur lors de la lecture du PDF : {str(e)}'}), 500
    finally:
        os.unlink(tmp_path)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

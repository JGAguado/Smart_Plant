from datetime import date

# Configuration file for the Sphinx documentation builder.

# -- Project information

project = 'Smart Plant'

author = 'J.G.Aguado'
email = 'jon-garcia@hotmail.com'

release = 'R1'
version = 'V2'

today = date.today().strftime("%B %d, %Y")
compile_date = today

# -- Project information

rst_epilog  = """
.. |Product| replace:: %s
.. |Author| replace:: %s
.. |Email| replace:: %s
.. |Version| replace:: %s%s
.. |Date| replace:: %s
""" % (project, author, email, version, release, compile_date)


# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx_copybutton',
    'sphinxcontrib.googleanalytics',

]

googleanalytics_id = "G-WPNFVPB451"

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

# Printables serves a Cloudflare browser challenge to automated link checkers;
# the community-model page remains a valid interactive browser link.
linkcheck_ignore = [r'https://www\.printables\.com/.*']

templates_path = ['_templates']

# -- Options for HTML output

html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'logo_only': True,
    'navigation_depth': 5,
}
html_context = {}

html_logo = "images/logo/White.png"
html_show_sourcelink = True
html_static_path = ['_static']

# -- Options for EPUB output
epub_show_urls = 'footnote'

def setup(app):
    app.add_css_file('my_theme.css')

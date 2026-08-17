# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SPHINX_BUILD"] = "1"

# -- Project information -----------------------------------------------------

project = 'eventsourcing'
copyright = '2025, John Bywater'
author = 'John Bywater'

# The full version, including alpha/beta/rc tags
# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#

# Avoid sphinx - pydnatic mixup: "Field "model_fields" conflicts with member ... of protected namespace "model_"."
# See https://github.com/pydantic/pydantic/discussions/7763 for workaround.

import examples.aggregate7.domainmodel
import examples.aggregate8.domainmodel
import examples.shopstandard.domain
import examples.shopstandard.application
import examples.shopvertical.events
import examples.shopvertical.common
import examples.shopvertical.slices.add_product_to_shop.cmd
import examples.shopvertical.slices.adjust_product_inventory.cmd
import examples.shopvertical.slices.list_products_in_shop.query
import examples.shopvertical.slices.get_cart_items.query
import examples.shopvertical.slices.add_item_to_cart.cmd
import examples.shopvertical.slices.remove_item_from_cart.cmd
import examples.shopvertical.slices.clear_cart.cmd
import examples.shopvertical.slices.submit_cart.cmd

from importlib.metadata import version as get_version

__version__ = get_version(project)

# The short X.Y version.
version = __version__
# The full version, including alpha/beta/rc tags.
release = __version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.viewcode',
    'sphinxcontrib.jquery',

]

autodoc_default_options = {
    'inherited-members': False,
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# list of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
pygments_style = 'sphinx'

import sphinx_rtd_theme
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# For the μ character in the "speedrun" reports.
# https://docs.readthedocs.com/platform/latest/guides/pdf-non-ascii-languages.html
latex_engine = "xelatex"

from pathlib import Path
from sphinx.environment.adapters.toctree import TocTree
from docutils.core import publish_parts
from sphinx.locale import _, __
from sphinx.transforms import SphinxTransform
from sphinx.util import logging
from docutils.io import DocTreeInput, StringOutput
from sphinx.util.docutils import SphinxTranslator, new_document
from sphinx.writers.html import HTMLWriter, HTMLTranslator
import docutils.nodes as nodes
import docutils.utils
import json
import os.path
import re
import sphinx.addnodes as addnodes
logger = logging.getLogger(__name__)

class TocVisitor1(SphinxTranslator):
    def __init__(self, document, builder, docname):
        super().__init__(document, builder)
        self.context=[]
        
    def visit_bullet_list(self, node):
        self.context.append([])

    def depart_bullet_list(self, node):
        contents = self.context.pop()
        content = self.builder.templates.render('toc_bullet_list.html',{"contents": ''.join(contents)})
        self.context.append(content)

    def visit_list_item(self, node):
        self.context.append([])

    def depart_list_item(self, node):
        contents = self.context.pop()
        content = self.builder.templates.render('toctree_entry.html',{"contents": ''.join(contents)})
        self.context.append(content)

    def visit_compact_paragraph(self, node):
        pass
    def depart_compact_paragraph(self, node):
        pass
    def render_partial(self, node):
        """Utility: Render a lone doctree node."""
        if node is None:
            return {'fragment': ''}
        doc = new_document('<partial node>')
        doc.append(node)

        writer = HTMLWriter(self.builder)
        val = publish_parts(reader_name='doctree',
                             writer=writer,
                             source_class=DocTreeInput,
                             settings_overrides={'output_encoding': 'unicode'},
                             source=doc)
        return (writer.document, val)

    def visit_reference(self, node):
        n2 = node.deepcopy()
        p = nodes.paragraph('', '', n2)
        assert n2.parent == p
        val = self.builder.render_partial(p)
#        print('%r', doc)
        
        render = val['body']
        print('2', render)
        render = re.sub(r"</p>$", '', re.sub(r"^<p>", '', render))
        print('1', render)
        result = re.match(r"<a([^>]*)>(.*)</a>$", render, re.MULTILINE)
        if result:
            linktext = result.group(2)
        else:
            linktext = None
            
        vars={"render": render, "linktext":  linktext,
              "att":{k:v for (k, v) in node.attlist()}}
#        print(json.dumps(vars, indent=4))
        content = self.builder.templates.render('reference.html',vars)
        self.context.append(content)
        raise nodes.SkipChildren

    def depart_reference(self, node):
        pass
    def visit_Text(self, node):
        pass
    def depart_Text(self, node):
        pass
    def visit_toctree(self, node):
        self.context.append([])
        
    def depart_toctree(self, node):
        contents = self.context.pop()
        content = self.builder.templates.render('toctree.html',
                                                {"contents": ''.join(contents)})
        self.context.append(content)

    def visit_caption(self, node):
        raise Exception
    def depart_caption(self, node):
        pass
    def unknown_visit(self, node):
        raise Exception
    def unknown_departure(self, node):
        pass

class TocTreeTemplater(SphinxTransform):
    default_priority = 900
    def apply(self, **kwargs):
        app = self.app
        builder = app.builder
        docname = app.env.docname
        toctree = app.env.tocs[docname]
        if toctree:
            visitor = TocVisitor1(self.document, builder, app.config.master_doc)
            toctree.walkabout(visitor)
            print('here1')
            toctree_html = ''.join(visitor.context.pop())
            setattr(app.env, 'toctree_html', toctree_html)
            toctree_html_node = nodes.raw('', toctree_html)
            for t in self.document.traverse(addnodes.toctree):
                i = t.parent.children.index(t)
                # I don't think this works.
                t.parent.children = [*t.parent.children[0:i - 1],
                                     toctree_html_node, *t.parent.children[i + 1:]]
        

def html_page_context(self, pagename, templatename, ctx, event_arg):
    if hasattr(self.env, 'toctree_html'):
        ctx['toc'] = self.env.toctree_html
        # toctree is a lambda - experimenting with trying to get this
        # html inserted
#        ctx['toctree'] = lambda **kw: self.env.toctree_html

    
def setup(app):
    app.connect('html-page-context', html_page_context)
    app.connect('doctree-resolved', doctree_resolved)
    app.add_post_transform(TocTreeTemplater)


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

class rel_links(nodes.Element): pass
class document_link(nodes.Element): pass
class document_ref(nodes.Element): pass
class document_links(nodes.Element): pass
class document_toctree(nodes.Element): pass
class local_toctree(nodes.Element): pass
class toctree_list(nodes.Element): pass
class toctree_list_item(nodes.Element): pass
class toctree_link(nodes.Element): pass
class links(nodes.Element): pass

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
        builder= app.builder

        docname = app.env.docname
        toctree = app.env.tocs[docname]#TocTree(app.env).get_toctree_for(master_doc, builder, False)
        if toctree:
            visitor = TocVisitor1(self.document, builder, app.config.master_doc)
#            visitor.new['master'] = True
            toctree.walkabout(visitor)
            print('here1')
            toctree_html = ''.join(visitor.context.pop())
            setattr(app.env, 'toctree_html', toctree_html)
            toctree_html_node = nodes.raw('', toctree_html)
            for t in self.document.traverse(addnodes.toctree):
                i = t.parent.children.index(t)
                t.parent.children = [*t.parent.children[0:i - 1],
                                     toctree_html_node, *t.parent.children[i + 1:]]
        

class TransformIndexNodes(SphinxTransform):
    default_priority = 900
    def apply(self, **kwargs):
        for node in self.document.traverse(addnodes.index):
            jsons = json.dumps(node['entries'])
            del node['entries']
            node['entries'] = jsons

class AddRelLinks(SphinxTransform):
    default_priority = 900
    def apply(self, **kwargs):
        self.relations = self.env.collect_relations()

        source = re.sub('\.[^\.]+$', '', self.document['source'])
        docname = os.path.relpath(source, self.app.srcdir)
        
        if docname not in self.relations:
            return
        
        links = self.relations[docname]
        links_elem = rel_links('', **{'xlink:type': 'extended'});

        relations = ['parent', 'previous', 'next']
        titles = ['Parent', __("Previous topic"), __("Next topic")]
        roles = {}
        for relation in relations:
            roles[relation] = 'http://heptet.us/linkprops/' + relation
            
        for link in links:
            relation = relations.pop(0)
            title = titles.pop(0)
            attr = {'xlink:title': title,
                    'xlink:role': roles[relation]}
            if link is not None:
                attr['xlink:href'] = link
                ref_elem = nodes.reference('', self.env.titles[link].astext(), refUri=link)
                link_elem = document_link('', ref_elem, **attr)
                links_elem.children.append(link_elem)
            else:
                link_elem = document_link('', **attr)
                links_elem.children.append(link_elem)
                
        self.document.children.insert(0, links_elem)

class AddXlinkNamespace(SphinxTransform):
    default_priority = 900
    def apply(self, **kwargs):
        self.document['xmlns:xlink'] = "http://www.w3.org/1999/xlink"

class RemoveDocumentSourceAttr(SphinxTransform):
    default_priority = 901
    def apply(self, **kwargs):
        if 'source' in self.document:
            del self.document['source']

class AddLocalToc(SphinxTransform):
    default_priority = 900
    def apply(self, **kwargs):
        source = re.sub('\.[^\.]+$', '', self.document['source'])
        docname = os.path.relpath(source, self.app.srcdir)
        self_toc = TocTree(self.env).get_toc_for(docname, self.app.builder)
        if self_toc and len(self_toc.children) > 0:
            lt_node = local_toctree('', self_toc);
            self.document.children.insert(0, lt_node);

# why isnt this a transform?
def doctree_read(app, doctree):
#    logger.warning('i am here! ' + repr(doctree.get('source')))
    links = []
    for ref in doctree.traverse(nodes.reference):
        name = ref.get('name', None)
        if not name:
            name = ref.get('refid', '')
        href = ref.get('refuri', None)
        if not href and 'refid' in ref:
            href = '#' + ref.get('refid')
        title = ref.astext()
        # how to label links??
        label = 'link_%s' % name
        attr = { 'xlink:href': href,
                 'xlink:title': title,
                 'xlink:label': label }
        
        link = document_link('', **attr)
#        logger.warning("link is %r", link.asdom())
        links.append(link)

    doctree.children.insert(0, document_links('', *links))

def doctree_resolved(app, doctree, docname):
    refs = []
    for ref in doctree.traverse(document_link):
        refs.append(ref.deepcopy())
        logger.warning('found link %s', ref['xlink:href'])

    if not hasattr(app.env, 'testext_refs'):
        env_refs = {}
        setattr(app.env, 'testext_refs', env_refs)
    else:
        env_refs = getattr(app.env, 'testext_refs')

    refs_dict = dict(refs=refs,
                     )
    env_refs[docname] = refs_dict


def build_finished(app, exception):
    if exception is not None:
        return
    links_elem = links('')
    document = docutils.utils.new_document('')
    document['xmlns:xlink'] = "http://www.w3.org/1999/xlink"
    for (docname, v) in app.env.testext_refs.items():

        doclink = document_ref('', **{'xmlns:href': docname,
                                      'xmlns:role': 'http://heptet.us/linkprops/document'})
        logger.info('%r', doclink)
        refs = v['refs']
        links_elem.children.insert(0, doclink)
        links_elem.children.extend(refs)

    class TocVisitor(SphinxTranslator):
        def __init__(self, document, builder, docname):
            super().__init__(document, builder)
            self.new = document_toctree('', docname=docname)
            self._current = [self.new]
        def visit_bullet_list(self, node):
            self._current.append(toctree_list(''))
        def depart_bullet_list(self, node):
            last = self._current.pop()
            self._current[-1].children.append(last)
        def visit_list_item(self, node):
            self._current.append(toctree_list_item(''))
        def depart_list_item(self, node):
            last = self._current.pop()
            self._current[-1].children.append(last)
        def visit_compact_paragraph(self, node):
            pass
        def depart_compact_paragraph(self, node):
            pass
        def visit_reference(self, node):
            attr = {'xlink:href': node['refuri']}
            self._current.append(toctree_link('', **attr))
        def depart_reference(self, node):
            last = self._current.pop()
            self._current[-1].children.append(last)
        def visit_Text(self, node):
            self._current.append(node.copy())
        def depart_Text(self, node):
            last = self._current.pop()
            self._current[-1].children.append(last)
        def visit_toctree(self, node):
            self._current.append(node.copy())
        def depart_toctree(self, node):
            last = self._current.pop()
            self._current[-1].children.append(last)
        def visit_caption(self, node):
            self._current.append(node.copy())
        def depart_caption(self, node):
            last = self._current.pop()
            self._current[-1].children.append(last)
        def unknown_visit(self, node):
            self._current.append(node.copy())
        def unknown_departure(self, node):
            last = self._current.pop()
            self._current[-1].children.append(last)

    master_doc = app.config.master_doc
    toctree = TocTree(app.env).get_toctree_for(master_doc, app.builder, False)
    if toctree:
        visitor = TocVisitor(document, app.builder, app.config.master_doc)
        visitor.new['master'] = True
        toctree.walkabout(visitor)
        document.children.append(visitor.new)
    
#    for (docname, toc) in app.env.tocs.items():
#    document.children.append(nodes.container('', toctree, ids=['global-toctree']))
#        toctree.walkabout(visitor)
#        visitor.new['master'] = docname == master_doc
#        document.children.append(visitor.new)

#        if docname == app.config.master_doc:
#            continue
#        my_toc = toc.deepcopy()
#        visitor = TocVisitor(document, app.builder, docname)
#        my_toc.walkabout(visitor)
#        document.children.append(visitor.new)
#
    document.children.append(links_elem)
    app.builder.write_doc('_links', document)

def html_page_context(self, pagename, templatename, ctx, event_arg):
    if hasattr(self.env, 'toctree_html'):
        ctx['toc'] = self.env.toctree_html
#        ctx['toctree'] = lambda **kw: self.env.toctree_html

    
def setup(app):
#    app.connect('doctree-read', doctree_read)
    app.connect('html-page-context', html_page_context)
    app.connect('doctree-resolved', doctree_resolved)
#    app.connect('build-finished', build_finished)
    app.add_node(rel_links)
    app.add_node(document_link)
    app.add_node(document_ref)
    app.add_node(document_links)
    app.add_node(document_toctree)
    app.add_node(local_toctree)
    app.add_node(toctree_list)
    app.add_node(toctree_list_item)
    app.add_node(toctree_link)
    app.add_node(links)
    app.add_post_transform(TransformIndexNodes)
#    app.add_post_transform(TransformTocTree)
    app.add_post_transform(TocTreeTemplater)
    #app.add_post_transform(AddLocalToc)
#    app.add_post_transform(AddXlinkNamespace)
    #app.add_post_transform(RemoveDocumentSourceAttr)
#    app.add_post_transform(AddRelLinks)

# coding: utf-8
from base64 import encodebytes
import io
import json
import os
from os.path import join as pjoin
import shutil
from shutil import which

import pytest
from jupyter_server.utils import url_path_join
from jupyter_server.tests.launchserver import ServerTestBase, assert_http_error
from nbformat import write
from nbformat.v4 import (
    new_notebook, new_markdown_cell, new_code_cell, new_output,
)


class NbconvertAPI(object):
    """Wrapper for nbconvert API calls."""

    def __init__(self, request):
        self.request = request

    def _req(self, verb, path, body=None, params=None):
        response = self.request(verb,
                url_path_join('nbconvert', path),
                data=body, params=params,
        )
        response.raise_for_status()
        return response

    def from_file(self, format, path, name, download=False):
        return self._req('GET', url_path_join(format, path, name),
                         params={'download': download})

    def from_post(self, format, nbmodel):
        body = json.dumps(nbmodel)
        return self._req('POST', format, body)

    def list_formats(self):
        return self._req('GET', '')


png_green_pixel = encodebytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00'
b'\x00\x00\x01\x00\x00x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT'
b'\x08\xd7c\x90\xfb\xcf\x00\x00\x02\\\x01\x1e.~d\x87\x00\x00\x00\x00IEND\xaeB`\x82'
).decode('ascii')


class APITest(ServerTestBase):
    def setUp(self):
        rootdir = self.root_dir

        if not os.path.isdir(pjoin(rootdir, 'foo')):
            subdir = pjoin(rootdir, 'foo')

            os.mkdir(subdir)

            # Make sure that we clean this up when we're done.
            # By using addCleanup this will happen correctly even if we fail
            # later in setUp.
            @self.addCleanup
            def cleanup_dir():
                shutil.rmtree(subdir, ignore_errors=True)

        nb = new_notebook()

        nb.cells.append(new_markdown_cell(u'Created by test ³'))
        cc1 = new_code_cell(source=u'print(2*6)')
        cc1.outputs.append(new_output(output_type="stream", text=u'12'))
        cc1.outputs.append(new_output(output_type="execute_result",
            data={'image/png': png_green_pixel},
            execution_count=1,
        ))
        nb.cells.append(cc1)

        with io.open(pjoin(rootdir, 'foo', 'testnb.ipynb'), 'w',
                     encoding='utf-8') as f:
            write(nb, f, version=4)

        self.nbconvert_api = NbconvertAPI(self.request)

    @pytest.mark.skipif(not which('pandoc'), reason='requires pandoc')
    def test_from_file(self):
        r = self.nbconvert_api.from_file('html', 'foo', 'testnb.ipynb')
        self.assertEqual(r.status_code, 200)
        self.assertIn(u'text/html', r.headers['Content-Type'])
        self.assertIn(u'Created by test', r.text)
        self.assertIn(u'print', r.text)

        r = self.nbconvert_api.from_file('python', 'foo', 'testnb.ipynb')
        self.assertIn(u'text/x-python', r.headers['Content-Type'])
        self.assertIn(u'print(2*6)', r.text)

    @pytest.mark.skipif(not which('pandoc'), reason='requires pandoc')
    def test_from_file_404(self):
        with assert_http_error(404):
            self.nbconvert_api.from_file('html', 'foo', 'thisdoesntexist.ipynb')

    @pytest.mark.skipif(not which('pandoc'), reason='requires pandoc')
    def test_from_file_download(self):
        r = self.nbconvert_api.from_file('python', 'foo', 'testnb.ipynb', download=True)
        content_disposition = r.headers['Content-Disposition']
        self.assertIn('attachment', content_disposition)
        self.assertIn('testnb.py', content_disposition)

    @pytest.mark.skipif(not which('pandoc'), reason='requires pandoc')
    def test_from_file_zip(self):
        r = self.nbconvert_api.from_file('latex', 'foo', 'testnb.ipynb', download=True)
        self.assertIn(u'application/zip', r.headers['Content-Type'])
        self.assertIn(u'.zip', r.headers['Content-Disposition'])

    @pytest.mark.skipif(not which('pandoc'), reason='requires pandoc')
    def test_from_post(self):
        nbmodel = self.request('GET', 'api/contents/foo/testnb.ipynb').json()

        r = self.nbconvert_api.from_post(format='html', nbmodel=nbmodel)
        self.assertEqual(r.status_code, 200)
        self.assertIn(u'text/html', r.headers['Content-Type'])
        self.assertIn(u'Created by test', r.text)
        self.assertIn(u'print', r.text)

        r = self.nbconvert_api.from_post(format='python', nbmodel=nbmodel)
        self.assertIn(u'text/x-python', r.headers['Content-Type'])
        self.assertIn(u'print(2*6)', r.text)

    @pytest.mark.skipif(not which('pandoc'), reason='requires pandoc')
    def test_from_post_zip(self):
        nbmodel = self.request('GET', 'api/contents/foo/testnb.ipynb').json()

        r = self.nbconvert_api.from_post(format='latex', nbmodel=nbmodel)
        self.assertIn(u'application/zip', r.headers['Content-Type'])
        self.assertIn(u'.zip', r.headers['Content-Disposition'])

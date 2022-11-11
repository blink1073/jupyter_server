import json
import os
import shutil
from base64 import encodebytes
from os.path import join as pjoin

import pytest
from nbformat import write
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output

png_green_pixel = encodebytes(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00"
    b"\x00\x00\x01\x00\x00x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
    b"\x08\xd7c\x90\xfb\xcf\x00\x00\x02\\\x01\x1e.~d\x87\x00\x00\x00\x00IEND\xaeB`\x82"
).decode("ascii")


@pytest.fixture
def notebook_file(tmpdir):
    nb = new_notebook()
    nb.cells.append(new_markdown_cell("Created by test ³"))
    cc1 = new_code_cell(source="print(2*6)")
    cc1.outputs.append(new_output(output_type="stream", text="12"))
    cc1.outputs.append(
        new_output(
            output_type="execute_result",
            data={"image/png": png_green_pixel},
            execution_count=1,
        )
    )
    nb.cells.append(cc1)

    os.mkdir(pjoin(tmpdir, "foo"))

    with open(pjoin(tmpdir, "foo", "testnb.ipynb"), "w", encoding="utf-8") as f:
        write(nb, f, version=4)


async def test_list_formats(jp_fetch):
    r = await jp_fetch("api", "nbconvert")
    formats = json.loads(r.body.decode())
    # Verify the type of the response.
    assert isinstance(formats, dict)
    # Verify that all returned formats have an
    # output mimetype defined.
    required_keys_present = []
    for _, data in formats.items():
        required_keys_present.append("output_mimetype" in data)
    assert all(required_keys_present), "All returned formats must have a `output_mimetype` key."


pandoc_guard = pytest.mark.skipif(
    not shutil.which("pandoc"), reason="Pandoc wasn't found. Skipping this test."
)


@pandoc_guard
async def test_from_file(notebook_file, jp_fetch):
    # TODO: this should be an html fetch
    r = await jp_fetch("api", "nbconvert", "html", "foo", "testnb.ipynb")
    assert r.status_code == 200
    assert "text/html" in r.headers["Content-Type"]
    assert "Created by test" in r.text
    assert "print" in r.text

    r = await jp_fetch("api", "nbconvert", "python", "foo", "testnb.ipynb")
    assert "text/x-python" in r.headers["Content-Type"]
    assert "print(2*6)" in r.text


@pandoc_guard
async def test_from_file_404(jp_fetch):
    with pytest.assertRaises(ValueError):
        await jp_fetch("api", "nbconvert", "html", "foo", "thisdoesntexist.ipynb")


@pandoc_guard
async def test_from_file_download(notebook_file, jp_fetch):
    r = jp_fetch("api", "nbconvert", "python", "foo", "testnb.ipynb", download=True)
    content_disposition = r.headers["Content-Disposition"]
    assert "attachment" in content_disposition
    assert "testnb.py" in content_disposition


# @pandoc_guard
# def test_from_file_zip(notebook_file, jp_fetch):
#     r = jp_fetch("api", "nbconvert", "latex", "foo", "testnb.ipynb", download=True)
#     assert "application/zip" in r.headers["Content-Type"]
#     assert ".zip" in r.headers["Content-Disposition"]


# @pandoc_guard
# def test_from_post(notebook_file, jp_fetch):
#     nbmodel = self.request("GET", "api/contents/foo/testnb.ipynb").json()

#     r = self.nbconvert_api.from_post(format="html", nbmodel=nbmodel)
#     self.assertEqual(r.status_code, 200)
#     self.assertIn("text/html", r.headers["Content-Type"])
#     self.assertIn("Created by test", r.text)
#     self.assertIn("print", r.text)

#     r = self.nbconvert_api.from_post(format="python", nbmodel=nbmodel)
#     self.assertIn("text/x-python", r.headers["Content-Type"])
#     self.assertIn("print(2*6)", r.text)


# @pandoc_guard
# def test_from_post_zip(notebook_file, jp_fetch):
#     nbmodel = self.request("GET", "api/contents/foo/testnb.ipynb").json()

#     r = self.nbconvert_api.from_post(format="latex", nbmodel=nbmodel)
#     self.assertIn("application/zip", r.headers["Content-Type"])
#     self.assertIn(".zip", r.headers["Content-Disposition"])

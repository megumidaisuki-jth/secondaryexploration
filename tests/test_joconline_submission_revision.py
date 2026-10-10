"""Read-only editorial/export checks; no simulations or resampling."""
import hashlib
import json
from pathlib import Path
import re
import unittest
import zipfile
from lxml import etree
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'manuscript/joconline-integrated-v1'
OUT = ROOT / 'manuscript/joconline-submission-v1'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class SubmissionRevisionTests(unittest.TestCase):
    def test_sealed_baseline_and_reused_evidence(self):
        manifest = json.loads((BASE/'manifest.json').read_bytes())
        self.assertEqual(len(manifest['files']), 34)
        for item in manifest['files']:
            path = ROOT/item['path']
            self.assertEqual(path.stat().st_size, item['bytes'])
            self.assertEqual(sha(path), item['sha256'])
        for folder in ('figures', 'source-data'):
            for path in (BASE/folder).iterdir():
                self.assertEqual(path.read_bytes(), (OUT/folder/path.name).read_bytes())
        self.assertEqual((BASE/'supplement.tex').read_bytes(), (OUT/'supplement.tex').read_bytes())

    def test_equations_and_results_unchanged(self):
        old = (BASE/'main.tex').read_text('utf-8')
        new = (OUT/'main.tex').read_text('utf-8')
        for pattern, count in [(r'\\begin\{equation\}(.*?)\\end\{equation\}',18), (r'\\\[(.*?)\\\]',2)]:
            original = re.findall(pattern, old, re.S)
            self.assertEqual(len(original), count)
            self.assertEqual(original, re.findall(pattern, new, re.S))
        start = r'\section{实验设计与统计方法}'
        end = r'\section*{数据与代码}'
        self.assertEqual(old.split(start)[1].split(end)[0], new.split(start)[1].split(end)[0])
        corrections = json.loads((ROOT/'manuscript/joconline-latex/accuracy-corrections.json').read_bytes())
        for item in corrections['replacements']:
            self.assertIn(item['new'], new, item['id'])

    def test_abstract_references_and_scope(self):
        text = (OUT/'main.tex').read_text('utf-8')
        abstract = text.split('摘要：')[1].split(r'\par}')[0]
        self.assertLessEqual(len(abstract.replace('$-$','-')), 200)
        keys = []
        for group in re.findall(r'\\upcite\{([^}]+)\}', text):
            for key in group.split(','):
                if key not in keys: keys.append(key)
        self.assertEqual(keys,[f'r{i}' for i in range(1,18)])
        self.assertEqual(re.findall(r'\\bibitem\{(r\d+)\}',text),keys)
        for marker in ('2512.11775v2','2609.03600v1','30:1-30:14','10.1016/j.hcc.2026.100443','不将关联坐标表示或守恒更新本身作为新模型'):
            self.assertIn(marker,text)

    def test_native_word_math_images_tables_captions(self):
        checks=json.loads((OUT/'word-checks.json').read_bytes())
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math','a':'http://schemas.openxmlformats.org/drawingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
        for name, maths, displays, images, tables in [('main',192,20,3,3),('supplement',13,0,8,2)]:
            path=OUT/(name+'.docx')
            self.assertEqual(sha(path),checks[name]['sha256'])
            self.assertEqual(checks[name]['conversion_warnings'],'')
            with zipfile.ZipFile(path) as archive:
                root=etree.fromstring(archive.read('word/document.xml'))
                self.assertEqual(len(root.xpath('//m:oMath',namespaces=ns)),maths)
                self.assertEqual(len(root.xpath('//m:oMathPara',namespaces=ns)),displays)
                self.assertEqual(len(root.xpath('//wp:inline',namespaces=ns)),images)
                self.assertEqual(len(root.xpath('//w:tbl',namespaces=ns)),tables)
                self.assertFalse(root.xpath('//w:pBdr',namespaces=ns))
                text=''.join(root.xpath('//w:t/text()|//m:t/text()',namespaces=ns))
                for n in range(1,images+1): self.assertIn('图'+('S' if name=='supplement' else '')+str(n)+' ',text)
                if name=='main':
                    for n in range(1,19): self.assertIn('('+str(n)+')',text)
                    for n in range(1,18): self.assertIn('['+str(n)+']',text)
                    self.assertNotIn('s3-ratio',text)
                    self.assertIn('式18是均值之比',text)
                self.assertNotIn(r'\begin{',text)
                self.assertNotIn(r'\upcite',text)

    def test_pdf_lengths_and_text(self):
        for name,pages in [('main',11),('supplement',10)]:
            reader=PdfReader(OUT/(name+'.pdf'))
            self.assertEqual(len(reader.pages),pages)
            self.assertTrue(all(p.extract_text().strip() for p in reader.pages))

if __name__=='__main__':
    unittest.main()

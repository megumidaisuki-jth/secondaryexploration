"""Display tests independent of plotting selectors; no simulation or inference."""
from fractions import Fraction
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from pypdf import PdfReader
from tools import build_s5_manuscript_figures as builder

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/supplement/initialization-ablation-figures-v1'

class DisplayTests(unittest.TestCase):
    def test_all_marks_exact_and_no_selection(self):
        source=json.loads((OUT/'source-data.json').read_bytes())
        ledger=json.loads((OUT/'display-ledger.json').read_bytes())
        mean_rows={(r['phase'],r['node_count'],r['metric'],r['arm']):r
                   for r in source['arm_means'] if r['scope']=='combined'}
        contrast_rows={(r['phase'],r['node_count'],r['metric'],r['comparison']):r
                       for r in source['comparisons'] if r['scope']=='combined'}
        seen_means=set(); seen_contrasts=set()
        for mark in ledger['marks']:
            key=(mark['phase'],mark['node_count'],mark['metric'],mark.get('arm',mark.get('comparison')))
            scale=100 if mark['metric']=='failure_risk' else 1
            if mark['kind']=='mean':
                row=mean_rows[key]
                self.assertEqual(mark['plotted'],float(Fraction(*row['estimate']))*scale)
                self.assertNotIn(key,seen_means); seen_means.add(key)
            else:
                row=contrast_rows[key]
                expected=[float(Fraction(*row['exact'][k]))*scale for k in ('lower','estimate','upper')]
                self.assertEqual(mark['plotted'],expected)
                self.assertEqual(mark['exact'],row['exact'])
                self.assertNotIn(key,seen_contrasts); seen_contrasts.add(key)
        self.assertEqual(seen_means,set(mean_rows))
        self.assertEqual(seen_contrasts,set(contrast_rows))

    def test_outputs_and_editable_text(self):
        for name in ['s5-arm-means','s5-topology-interaction','s5-initialization']:
            for suffix in ['pdf','svg','png','tiff']:
                self.assertGreater((OUT/f'{name}.{suffix}').stat().st_size,1000)
            pdf=PdfReader(OUT/f'{name}.pdf')
            self.assertEqual(len(pdf.pages),1)
            self.assertAlmostEqual(float(pdf.pages[0].mediabox.width)*25.4/72,170,places=4)
            self.assertIn('节点数',pdf.pages[0].extract_text())
            self.assertIn('<text',(OUT/f'{name}.svg').read_text(encoding='utf-8'))

    def test_provenance_and_no_recomputation(self):
        self.assertEqual(builder.sha(OUT/'source-data.json'),builder.SOURCE_SHA)
        self.assertEqual(builder.sha(ROOT/'manuscript/joconline-latex/main.tex'),builder.TEX_SHA)
        data=builder.load_verified()
        self.assertEqual(len(data['comparisons']),240)
        ledger=json.loads((OUT/'display-ledger.json').read_bytes())
        self.assertEqual(ledger['new_simulations'],0)
        self.assertEqual(ledger['new_bootstrap_replicates'],0)
        with patch.object(builder,'SOURCE_SHA','0'*64):
            with self.assertRaises(AssertionError): builder.load_verified()
        with patch.object(builder,'PROOF_SHA','0'*64):
            with self.assertRaises(AssertionError): builder.load_verified()

    def test_revision_keeps_original_corrections(self):
        paper=ROOT/'manuscript/joconline-s5-revision-v1'
        tex=(paper/'main.tex').read_text(encoding='utf-8')
        corrections=json.loads((ROOT/'manuscript/joconline-latex/accuracy-corrections.json').read_bytes())
        for correction in corrections['replacements']:
            self.assertIn(correction['new'],tex)
        self.assertEqual(tex.count(r'\label{eq:s5-interaction}'),1)
        self.assertIn('不是新的预注册或盲确认实验',tex)
        self.assertIn('未作多重比较校正',tex)
        self.assertIn('不是16个独立重复或统计检验',tex)

if __name__=='__main__': unittest.main()

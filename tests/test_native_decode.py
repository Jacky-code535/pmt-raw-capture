from pathlib import Path
import base64
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pmt.decode.unit_converter import Formula
from pmt.decode.schema_loader import read_xml
from pmt.decode.payload_decoder import PayloadDecoder
from pmt.decode.layout_parser import Layout
from pmt.decode.platform_data import validate
import shutil
import copy
import xml.etree.ElementTree as ET


class FormulaTest(unittest.TestCase):
    def test_xml_square_root(self):
        formula = Formula("sqrt(($parameter_1 * $parameter_0 - $parameter_2 ** 2) / ($parameter_1 * ($parameter_1 - 1))) * 0.1")
        self.assertEqual(formula.names, {"parameter_0", "parameter_1", "parameter_2"})
        self.assertAlmostEqual(formula.evaluate({"parameter_0": 20, "parameter_1": 2, "parameter_2": 4}), (12 ** 0.5) * 0.1)
        for expression in ("sqrt()", "sqrt(1, 2)", "sqrt(value=1)", "math.sqrt(1)"):
            with self.assertRaises(ValueError):
                Formula(expression)

    def test_validation_rejects_unsupported_nodes_without_evaluation(self):
        for expression in ("fn(value)", "value.attr", "value[0]", "[1, 2]", "'text'", "value ? 1 : 2", None):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                Formula(expression)
        with self.assertRaises(ValueError):
            Formula("((2 ** 64) ** 64) ** 64").evaluate({})

    def test_arithmetic_and_integer_precision(self):
        self.assertEqual(Formula("$parameter_0 / 25e6").evaluate({"parameter_0": 50000000}), 2)
        self.assertEqual(Formula("$value & 255").evaluate({"value": 2**63 + 3}), 3)
        self.assertEqual(Formula("$value").evaluate({"value": 2**63 + 3}), 2**63 + 3)

    def test_rejects_code_execution_and_unbounded_shift(self):
        for expression in ("__import__('os').system('true')", "value.__class__", "1 << 1000", "2 ** 1000"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                Formula(expression).evaluate({"value": 1})


class NativeDecodeTest(unittest.TestCase):
    def test_counter_names_keep_xml_group_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "xml"
            shutil.copytree(Path(__file__).parent / "fixtures/synthetic_raw", root)
            path = root / "schema/interface.xml"
            tree = ET.parse(path)
            samples = tree.getroot().find("AggregatorSamples")
            first = samples.find("T_AggregatorSample")
            first.find("SampleType").text = "Counter"
            second = copy.deepcopy(first)
            second.set("sampleGroup", "other_clock")
            samples.append(second)
            tree.write(path)
            decoder = PayloadDecoder(root / "pmt.xml")
            metrics = decoder.decode({"TelemetryData": [{"Guid": "0x1234", "Size": 8,
                "Data": base64.b64encode((250 << 8).to_bytes(8, "little")).decode()}]})[0]["result"]["metrics"]
            self.assertEqual([metric["name"] for metric in metrics], ["clock.elapsed", "other_clock.elapsed"])
            self.assertEqual([metric["value"] for metric in metrics], [25, 25])

    def test_mapping_success_does_not_hide_missing_formula(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "xml"
            shutil.copytree(Path(__file__).parent / "fixtures/synthetic_raw", root)
            path = root / "schema/interface.xml"
            path.write_text(path.read_text().replace('<transformREF>scale</transformREF>', '<transformREF>missing</transformREF>'))
            report = validate(root / "pmt.xml")
            self.assertTrue(report["mapping_valid"])
            self.assertFalse(report["valid"])
            self.assertEqual(report["mapping_count"], 1)
            self.assertEqual(report["schema_count"], 0)
            self.assertEqual(report["errors"][0]["stage"], "decode_schema")
            self.assertIn("unknown transform: missing", report["errors"][0]["error"])
            self.assertEqual(report["errors"][0]["files"]["aggregatorinterface"], str(path))

    def test_layout_resolves_group_scoped_duplicate_names(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.xml"
            path.write_text('<Aggregator><uniqueid>0x1234</uniqueid>' + ''.join(
                '<SampleGroup sampleID="%s" sampleGroupID="Container_%s"><length>64</length>'
                '<sample sampleID="value"><lsb>0</lsb><msb>63</msb></sample>'
                '<sample sampleID="RESERVED"><lsb>64</lsb><msb>95</msb></sample></SampleGroup>' % (index, index)
                for index in range(2)) + '</Aggregator>')
            layout = Layout(path, 16, {"value"})
            raw = layout.extract((7).to_bytes(8, "little") + (9).to_bytes(8, "little"))
            self.assertEqual(raw[layout.resolve("value", "Container_0")], 7)
            self.assertEqual(raw[layout.resolve("value", "Container_1")], 9)
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                layout.resolve("value")
            with self.assertRaisesRegex(ValueError, "unknown"):
                layout.resolve("value", "Container_2")
            with self.assertRaisesRegex(ValueError, "invalid PMT bit range"):
                Layout(path, 16, {"RESERVED"})

    def test_exact_xml_decode_and_invalid_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "schema").mkdir()
            (root / "pmt.xml").write_text('<pmt><mappings><mapping guid="0x1234" size="8"><xmlset><basedir>schema</basedir><common>common.xml</common><aggregator>layout.xml</aggregator><aggregatorinterface>interface.xml</aggregatorinterface></xmlset></mapping></mappings></pmt>')
            (root / "schema/common.xml").write_text('<DataTypes><dataType datatypeID="time"><units name="seconds"/></dataType></DataTypes>')
            (root / "schema/layout.xml").write_text('<!DOCTYPE Aggregator [<!ENTITY otherfile SYSTEM "file:///nonexistent">]><Aggregator><DataTypesInclude>&otherfile;</DataTypesInclude><uniqueid>0x1234</uniqueid><SampleGroup sampleID="0"><length>64</length><sample sampleID="ticks"><lsb>8</lsb><msb>39</msb></sample></SampleGroup></Aggregator>')
            (root / "schema/interface.xml").write_text('<AggregatorInterface><uniqueid>0x1234</uniqueid><TransFormations><TransFormation transformID="scale"><transform>$parameter_0 / 10</transform></TransFormation></TransFormations><AggregatorSamples><T_AggregatorSample sampleName="elapsed" sampleGroup="clock" datatypeIDREF="time"><SampleType>Snapshot</SampleType><TransFormInputs><TransFormInput varName="parameter_0"><sampleIDREF>ticks</sampleIDREF></TransFormInput></TransFormInputs><transformREF>scale</transformREF></T_AggregatorSample></AggregatorSamples></AggregatorInterface>')
            decoder = PayloadDecoder(root / "pmt.xml")
            item = {"Guid": "0x00001234", "Size": 8, "Data": base64.b64encode((250 << 8).to_bytes(8, "little")).decode()}
            result = decoder.decode({"TelemetryData": [item]})[0]["result"]
            self.assertEqual(result["metrics"], [{"name": "clock.elapsed", "type": "gauge", "unit": "seconds", "value": 25}])
            with self.assertRaisesRegex(ValueError, "no exact"):
                decoder.schema("0x1234", 16)
            (root / "entity.xml").write_text('<!DOCTYPE test [<!ENTITY expand "boom">]><test>&expand;</test>')
            with self.assertRaisesRegex(ValueError, "entities"):
                read_xml(root / "entity.xml")
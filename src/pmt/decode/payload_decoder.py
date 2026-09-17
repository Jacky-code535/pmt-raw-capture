"""In-process exact-schema decoder; no network calls during analysis."""

import base64
import re

from .layout_parser import Layout
from .schema_loader import SchemaRegistry, guid_number, read_xml
from .unit_converter import Formula


class PayloadDecoder:
    def __init__(self, metadata):
        self.registry = SchemaRegistry(metadata)
        self.cache = {}

    def schema(self, guid, size):
        key = (guid_number(guid), int(size))
        if key in self.cache:
            return self.cache[key]
        paths = self.registry.select(guid, size)
        interface = read_xml(paths["aggregatorinterface"])
        entries = [entry for entry in interface.findall("./AggregatorSamples/T_AggregatorSample")
               if not re.search(r"RESERVED|RSVD", entry.attrib["sampleName"], re.IGNORECASE)]
        required_names = {node.findtext("sampleIDREF") for entry in entries
                  for node in entry.findall("./TransFormInputs/TransFormInput")}
        layout = Layout(paths["aggregator"], size, required_names)
        if int(layout.guid, 16) != key[0] or int(interface.findtext("uniqueid"), 16) != key[0]:
            raise ValueError("XML identity differs from registry mapping")
        units = {entry.attrib["datatypeID"]: entry.find("units").get("name", "") if entry.find("units") is not None else ""
                 for entry in read_xml(paths["common"]).findall("dataType")}
        formulas = {}
        for entry in interface.findall("./TransFormations/TransFormation"):
            name = entry.attrib["transformID"]
            if name in formulas:
                raise ValueError("duplicate transform ID")
            formulas[name] = Formula(entry.findtext("transform"))
        metrics = []
        names = set()
        for entry in entries:
            sample_name = entry.attrib["sampleName"]
            kind = "counter" if entry.findtext("SampleType") == "Counter" else "gauge"
            name = entry.attrib["sampleGroup"] + "." + sample_name
            name = name.replace("[", ".").replace("]", "")
            if name in names:
                raise ValueError("duplicate metric name: " + name)
            names.add(name)
            inputs = {}
            for input_node in entry.findall("./TransFormInputs/TransFormInput"):
                sample_id = input_node.findtext("sampleIDREF")
                variable = input_node.attrib["varName"]
                if variable in inputs:
                    raise ValueError("duplicate transform input")
                inputs[variable] = layout.resolve(sample_id, input_node.findtext("sampleGroupIDREF"))
            transform = entry.findtext("transformREF")
            if transform not in formulas:
                raise ValueError("unknown transform: " + str(transform))
            if not formulas[transform].names.issubset(inputs):
                raise ValueError("formula references undefined inputs for metric: " + name)
            datatype = entry.attrib["datatypeIDREF"]
            if datatype not in units:
                raise ValueError("unknown datatype: " + datatype)
            metrics.append((name, kind, units[datatype], formulas[transform], inputs))
        if not metrics:
            raise ValueError("schema produced no metric definitions")
        self.cache[key] = (layout, metrics)
        return layout, metrics

    def decode(self, document):
        records = []
        for index, item in enumerate(document["TelemetryData"]):
            payload = base64.b64decode(item["Data"], validate=True)
            size = int(item["Size"])
            if len(payload) != size:
                raise ValueError("payload length differs from reported Size")
            layout, definitions = self.schema(item["Guid"], size)
            raw = layout.extract(payload)
            metrics = []
            for name, kind, unit, formula, inputs in definitions:
                try:
                    value = formula.evaluate({variable: raw[sample] for variable, sample in inputs.items()})
                except (KeyError, ArithmeticError, ValueError) as error:
                    raise ValueError("metric %s: %s" % (name, error)) from error
                metrics.append({"name": name, "type": kind, "unit": unit, "value": value})
            records.append({"index": index, "result": {"guid": item["Guid"], "reported_size_bytes": size,
                            "exact_guid_size_match": True, "metrics": metrics}})
        return records
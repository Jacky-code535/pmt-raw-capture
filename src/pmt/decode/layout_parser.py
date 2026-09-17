"""Parse Intel PMT 64-bit sample containers without platform field tables."""

from .schema_loader import read_xml


class Layout:
    def __init__(self, path, size, required_names=None):
        root = read_xml(path)
        self.guid = root.findtext("uniqueid")
        self.fields = {}
        self.by_name = {}
        for group in root.findall("SampleGroup"):
            if int(group.findtext("length", "64")) != 64:
                raise ValueError("only 64-bit PMT containers are supported")
            offset = int(group.attrib["sampleID"]) * 8
            if offset < 0 or offset + 8 > size:
                raise ValueError("XML container outside reported payload")
            for sample in group.findall("sample"):
                name = sample.attrib["sampleID"]
                if required_names is not None and name not in required_names:
                    continue
                key = (group.get("sampleGroupID", group.get("name", "")), name)
                if key in self.fields:
                    raise ValueError("duplicate layout sample identity: " + repr(key))
                low, high = int(sample.findtext("lsb")), int(sample.findtext("msb"))
                if not 0 <= low <= high < 64:
                    raise ValueError("invalid PMT bit range for %s: %s..%s" % (name, low, high))
                self.fields[key] = (offset, low, high - low + 1)
                self.by_name.setdefault(name, []).append(key)
        if not self.fields:
            raise ValueError("XML contains no sample fields")

    def resolve(self, name, group=None):
        if group is not None:
            key = (group, name)
            if key not in self.fields:
                raise ValueError("unknown sample reference: " + repr(key))
            return key
        matches = self.by_name.get(name, [])
        if len(matches) != 1:
            raise ValueError("missing or ambiguous sample reference: " + str(name))
        return matches[0]

    def extract(self, payload):
        values = {}
        for name, (offset, low, width) in self.fields.items():
            container = int.from_bytes(payload[offset:offset + 8], "little")
            values[name] = (container >> low) & ((1 << width) - 1)
        return values
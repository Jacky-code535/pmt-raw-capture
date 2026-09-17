"""Exact GUID/length registry with non-resolving XML parsing."""

from pathlib import Path
from xml.parsers import expat
import xml.etree.ElementTree as ET


def read_xml(path):
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("XML file exceeds 32 MiB limit")
    builder = ET.TreeBuilder()
    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartElementHandler = lambda name, attrs: builder.start(name.rsplit("}", 1)[-1], attrs)
    parser.EndElementHandler = lambda name: builder.end(name.rsplit("}", 1)[-1])
    parser.CharacterDataHandler = builder.data

    def entity(name, parameter, value, base, system, public, notation):
        if value is not None or parameter:
            raise ValueError("internal and parameter XML entities are not supported")

    parser.EntityDeclHandler = entity
    parser.ExternalEntityRefHandler = lambda *arguments: 1
    try:
        parser.Parse(path.read_bytes(), True)
        return builder.close()
    except expat.ExpatError as error:
        raise ValueError("invalid XML %s: %s" % (path, error)) from error


def guid_number(value):
    if not str(value).lower().startswith("0x"):
        raise ValueError("GUID must begin with 0x")
    return int(value, 16)


class SchemaRegistry:
    def __init__(self, metadata):
        self.path = Path(metadata).resolve()
        self.entries = {}
        for mapping in read_xml(self.path).findall("./mappings/mapping"):
            key = (guid_number(mapping.attrib["guid"]), int(mapping.attrib["size"]))
            if key in self.entries:
                raise ValueError("duplicate GUID+Size registry mapping: " + str(key))
            self.entries[key] = mapping
        if not self.entries:
            raise ValueError("empty PMT registry")

    def select(self, guid, size):
        key = (guid_number(guid), int(size))
        if key not in self.entries:
            raise ValueError("no exact XML mapping for %s, %s bytes" % (guid, size))
        xmlset = self.entries[key].find("xmlset")
        if xmlset is None:
            raise ValueError("missing XML set")
        result = {}
        for tag in ("common", "aggregator", "aggregatorinterface"):
            base, filename = xmlset.findtext("basedir"), xmlset.findtext(tag)
            if not base or not filename:
                raise ValueError("incomplete XML set")
            relative = Path(base) / filename
            resolved = (self.path.parent / relative).resolve()
            if relative.is_absolute() or ".." in relative.parts or self.path.parent not in resolved.parents:
                raise ValueError("XML reference escapes registry directory")
            if not resolved.is_file():
                raise ValueError("missing schema file: " + str(resolved))
            result[tag] = resolved
        return result
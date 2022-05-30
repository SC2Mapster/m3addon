#!/usr/bin/python3
# -*- coding: utf-8 -*-

import m3
import sys


structureName = sys.argv[1]
structureVersion = int(sys.argv[2])
mdVersion = sys.argv[3] if len(sys.argv) > 3 else 'MD34'

structureDescription = m3.structures[structureName].getVersion(structureVersion, mdVersion, True)  # type: m3.M3StructureDescription
if structureDescription is None:
    raise Exception("The structure %s hasn't been defined in version %d" % (structureName, structureVersion))
offset = 0
for field in structureDescription.fields:
    print("0x%03X %04d %s" % (offset, offset, field.name))
    offset += field.size


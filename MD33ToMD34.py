#!/usr/bin/python3
# -*- coding: utf-8 -*-

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import m3
import argparse
import os.path
from typing import Optional
import os


def structureToMD34(structure: m3.M3Structure):
    structure.structureDescription = m3.structures[structure.structureDescription.structureName].getVersion(structure.structureDescription.structureVersion)
    for field in structure.structureDescription.fields:
        value = getattr(structure, field.name)
        if isinstance(value, list) and len(value) > 0:
            for subValue in value:
                if isinstance(subValue, m3.M3Structure):
                    structureToMD34(subValue)
                elif isinstance(subValue, (int, float, list, str, bytes, bytearray)) or subValue is None:
                    pass
                else:
                    raise Exception(field.name, type(subValue), subValue)
        elif isinstance(value, m3.M3Structure):
            structureToMD34(value)
        elif isinstance(value, (int, float, list, str, bytes, bytearray)) or value is None:
            pass
        else:
            raise Exception(field.name, type(value), value)


def processModel(mSrc: str, mDest: Optional[str] = None, outDir: Optional[str] = None, skipExisting: bool = False):
    if not outDir:
        outDir = os.path.dirname(mSrc)
    if not mDest:
        tmp = os.path.basename(mSrc).split('.')
        name = ''.join(tmp[:-1]) if len(tmp) > 1 else tmp[0]
        mDest = os.path.join(outDir, name + '_MD34.m3')

    print("%s -> %s ... " % (mSrc, mDest), end='')

    if skipExisting and os.path.isfile(mDest):
        print("SKIPPED")
        return

    try:
        model = m3.loadModel(mSrc)
        structureToMD34(model)
        m3.saveAndInvalidateModel(model, mDest)
        print("OK")
    except Exception:
        print("FAIL")
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert Starcraft II Beta model (MD33) to its supported variant (MD34)')
    parser.add_argument('src', type=str, nargs='+', help='source .m3 file')
    parser.add_argument('-O', '--output-directory', type=str, help='output directory for converted m3 files')
    parser.add_argument('--skip-existing', action='store_true', default=False, help='skip conversion if target field already exists')
    args = parser.parse_args()
    for src in args.src:
        processModel(src, None, args.output_directory, args.skip_existing)

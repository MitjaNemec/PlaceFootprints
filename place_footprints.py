# -*- coding: utf-8 -*-
#  place_footprints.py
#
# Copyright (C) 2022 Mitja Nemec
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
import pcbnew
from collections import namedtuple
import os
import logging
import itertools
import math


SCALE = 1000000.0

Footprint = namedtuple('Footprint', ['ref', 'fp', 'fp_id', 'sheet_id', 'filename'])
logger = logging.getLogger(__name__)


def rotate_around_center(coordinates, angle):
    """ rotate coordinates for a defined angle in degrees around coordinate center"""
    new_x = coordinates[0] * math.cos(2 * math.pi * angle/360)\
          - coordinates[1] * math.sin(2 * math.pi * angle/360)
    new_y = coordinates[0] * math.sin(2 * math.pi * angle/360)\
          + coordinates[1] * math.cos(2 * math.pi * angle/360)
    return new_x, new_y


def rotate_around_point(old_position, point, angle):
    """ rotate coordinates for a defined angle in degrees around a point """
    # get relative position to point
    rel_x = old_position[0] - point[0]
    rel_y = old_position[1] - point[1]
    # rotate around
    new_rel_x, new_rel_y = rotate_around_center((rel_x, rel_y), angle)
    # get absolute position
    new_position = (new_rel_x + point[0], new_rel_y + point[1])
    return new_position


def get_index_of_tuple(list_of_tuples, index, value):
    for pos, t in enumerate(list_of_tuples):
        if t[index] == value:
            return pos


class Placer:
    @staticmethod
    def get_footprint_id(footprint):
        path = footprint.GetPath().AsString().upper().replace('00000000-0000-0000-0000-0000', '').split("/")
        if len(path) != 1:
            fp_id = path[-1]
        # if path is empty, then footprint is not part of schematics
        else:
            fp_id = None
        return fp_id

    @staticmethod
    def get_sheet_id(footprint):
        path = footprint.GetPath().AsString().upper().replace('00000000-0000-0000-0000-0000', '').split("/")
        if len(path) != 1:
            sheet_id = path[-2]
        # if path is empty, then footprint is not part of schematics
        else:
            sheet_id = None
        return sheet_id

    def get_sheet_path(self, footprint):
        """ get sheet id """
        path = footprint.GetPath().AsString().upper().replace('00000000-0000-0000-0000-0000', '').split("/")
        if len(path) != 1:
            sheet_path = path[0:-1]
            sheet_names = [self.dict_of_sheets[x][0] for x in sheet_path if x in self.dict_of_sheets]
            sheet_files = [self.dict_of_sheets[x][1] for x in sheet_path if x in self.dict_of_sheets]
            sheet_path = [sheet_names, sheet_files]
        else:
            sheet_path = ["", ""]
        return sheet_path

    def get_fp_by_ref(self, ref):
        for fp in self.footprints:
            if fp.ref == ref:
                return fp
        return None

    def get_footprints_with_reference_designator(self, ref_des):
        list_of_footprints = []
        for fp in self.footprints:
            index = 0
            for i in range(len(fp.ref)):
                if not fp.ref[i].isdigit():
                    index = i+1
            fp_des = fp.ref[:index]
            if fp_des == ref_des:
                list_of_footprints.append(fp.ref)
        return list_of_footprints

    def __init__(self, board):
        self.board = board
        self.pcb_filename = os.path.abspath(board.GetFileName())
        self.sch_filename = self.pcb_filename.replace(".kicad_pcb", ".kicad_sch")
        self.project_folder = os.path.dirname(self.pcb_filename)

        # construct a list of footprints with all pertinent data
        logger.info('getting a list of all footprints on board')
        footprints = board.GetFootprints()
        self.footprints = []

        # get dict_of_sheets from layout data only (through footprint Sheetfile and Sheetname properties)
        self.dict_of_sheets = {}
        unique_sheet_ids = set()
        for fp in footprints:
            # construct a set of unique sheets from footprint properties
            path = fp.GetPath().AsString().upper().replace('00000000-0000-0000-0000-0000', '').split("/")
            sheet_path = path[0:-1]
            for x in sheet_path:
                unique_sheet_ids.add(x)

            sheet_id = self.get_sheet_id(fp)
            try:
                sheet_file = fp.GetProperty('Sheetfile')
                sheet_name = fp.GetProperty('Sheetname')
            except KeyError:
                logger.info("Footprint " + fp.GetReference() +
                            " does not have Sheetfile property, it will not be considered for placement."
                            " Most likely it is only in layout")
                continue
            # footprint is in the schematics and has Sheetfile property
            if sheet_file and sheet_id:
                # strip prepending "File: " if existing
                self.dict_of_sheets[sheet_id] = [sheet_name, sheet_file]
            # footprint is in the schematics but has no Sheetfile properties
            elif sheet_id:
                logger.info("Footprint " + fp.GetReference() + " does not have Sheetfile property")
                raise LookupError("Footprint " + str(
                    fp.GetReference()) + " doesn't have Sheetfile and Sheetname properties. "
                                         "You need to update the layout from schematics")
            # footprint is on root level
            else:
                logger.info("Footprint " + fp.GetReference() + " on root level")

        # catch corner cases with nested hierarchy, where some hierarchical pages don't have any footprints
        unique_sheet_ids.remove("")
        if len(unique_sheet_ids) > len(self.dict_of_sheets):
            # open root schematics file and parse for other schematics files
            # This might be prone to errors regarding path discovery
            # thus it is used only in corner cases
            schematic_found = {}
            self.parse_schematic_files(self.sch_filename, schematic_found)
            self.dict_of_sheets = schematic_found

        for fp in footprints:
            try:
                sheet_file = fp.GetProperty('Sheetfile')
                # construct a list of all the footprints
                mod_named_tuple = Footprint(fp=fp,
                                            fp_id=self.get_footprint_id(fp),
                                            sheet_id=self.get_sheet_path(fp)[0],
                                            filename=self.get_sheet_path(fp)[1],
                                            ref=fp.GetReference())
                self.footprints.append(mod_named_tuple)
            except KeyError:
                pass
        pass

    def parse_schematic_files(self, filename, dict_of_sheets):
        with open(filename) as f:
            contents = f.read().split("\n")
        # find (sheet (at and then look in next few lines for new schematics file
        for i in range(len(contents)):
            line = contents[i]
            if "(sheet (at" in line:
                sheetname = ""
                sheetfile = ""
                sheet_id = ""
                for j in range(i,i+10):
                    if "(uuid " in contents[j]:
                        sheet_id = contents[j].lstrip("(uuid ").rstrip(")")
                    if "(property \"Sheet name\"" in contents[j]:
                        sheetname = contents[j].lstrip("(property \"Sheet name\"").split()[0].replace("\"", "")
                    if "(property \"Sheet file\"" in contents[j]:
                        sheetfile = contents[j].lstrip("(property \"Sheet file\"").split()[0].replace("\"", "")
                # here I should find all sheet data
                dict_of_sheets[sheet_id] = [sheetname, sheetfile]
                # open a newfound file and look for nested sheets
                self.parse_schematic_files(sheetfile, dict_of_sheets)
        return

    def get_list_of_footprints_with_same_id(self, fp_id):
        footprints_with_same_id = []
        for fp in self.footprints:
            if fp.fp_id == fp_id:
                footprints_with_same_id.append(fp)
        return footprints_with_same_id

    def get_sheets_to_replicate(self, reference_footprint, level):
        sheet_id = reference_footprint.sheet_id
        sheet_file = reference_footprint.filename
        # find level_id
        level_file = sheet_file[sheet_id.index(level)]
        logger.info('constructing a list of sheets suitable for replication on level:'
                    + repr(level) + ", file:" + repr(level_file))

        # construct complete hierarchy path up to the level of reference footprint
        sheet_id_up_to_level = []
        for i in range(len(sheet_id)):
            sheet_id_up_to_level.append(sheet_id[i])
            if sheet_id[i] == level:
                break

        # get all footprints with same ID
        footprints_with_same_id = self.get_list_of_footprints_with_same_id(reference_footprint.fp_id)
        # if hierarchy is deeper, match only the sheets with same hierarchy from root to -1
        sheets_on_same_level = []

        # go through all the footprints
        for fp in footprints_with_same_id:
            # if the footprint is on selected level, it's sheet is added to the list of sheets on this level
            if level_file in fp.filename:
                sheet_id_list = []
                # create a hierarchy path only up to the level
                for i in range(len(fp.filename)):
                    sheet_id_list.append(fp.sheet_id[i])
                    if fp.filename[i] == level_file:
                        break
                sheets_on_same_level.append(sheet_id_list)

        # remove duplicates
        sheets_on_same_level.sort()
        sheets_on_same_level = list(k for k, _ in itertools.groupby(sheets_on_same_level))

        # remove the sheet path for reference footprint
        if sheet_id_up_to_level in sheets_on_same_level:
            index = sheets_on_same_level.index(sheet_id_up_to_level)
            del sheets_on_same_level[index]
        logger.info("suitable sheets are:"+repr(sheets_on_same_level))
        return sheets_on_same_level

    def get_footprints_on_sheet(self, level):
        footprints_on_sheet = []
        level_depth = len(level)
        for fp in self.footprints:
            if level == fp.sheet_id[0:level_depth]:
                footprints_on_sheet.append(fp)
        return footprints_on_sheet

    def get_footprints_not_on_sheet(self, level):
        footprints_not_on_sheet = []
        level_depth = len(level)
        for fp in self.footprints:
            if level != fp.sheet_id[0:level_depth]:
                footprints_not_on_sheet.append(fp)
        return footprints_not_on_sheet

    @staticmethod
    def get_footprints_bounding_box(footprints):
        # get the first bounding box
        bounding_box = footprints[0].fp.GetBoundingBox()
        top = bounding_box.GetTop()
        bottom = bounding_box.GetBottom()
        left = bounding_box.GetLeft()
        right = bounding_box.GetRight()
        # iterate throught the rest of the footprints
        # and resize the bounding box accordingly
        for fp in footprints:
            fp_box = fp.fp.GetBoundingBox()
            top = min(top, fp_box.GetTop())
            bottom = max(bottom, fp_box.GetBottom())
            left = min(left, fp_box.GetLeft())
            right = max(right, fp_box.GetRight())
        return top, bottom, left, right

    def get_footprints_bounding_box_size(self, footprints):
        top, bottom, left, right = self.get_footprints_bounding_box(footprints)
        height = (bottom-top)/1000000.0
        width = (right-left)/1000000.0
        return height, width

    def get_footprints_bounding_box_center(self, footprints):
        top, bottom, left, right = self.get_footprints_bounding_box(footprints)
        pos_y = (bottom+top)/2
        pos_x = (right+left)/2
        return pos_x, pos_y

    def place_circular(self, footprints_to_place, reference_footprint, radius, delta_angle, step, rotation,
                       copy_text_items):
        logger.info("Starting placing with circular layout")
        # get proper footprint list
        footprints = []
        for fp in footprints_to_place:
            footprints.append(self.get_fp_by_ref(fp))

        ref_fp = self.get_fp_by_ref(reference_footprint)

        # get first footprint position
        ref_fp_pos = ref_fp.fp.GetPosition()
        logger.info("reference footprint position at: " + repr(ref_fp_pos))
        ref_fp_index = footprints.index(ref_fp)

        point_of_rotation = (ref_fp_pos[0], ref_fp_pos[1] + radius * SCALE)

        logger.info("rotation center at: " + repr(point_of_rotation))
        for fp in footprints:
            index = footprints.index(fp)
            delta_index = index - ref_fp_index

            if fp.fp.IsFlipped() != ref_fp.fp.IsFlipped():
                fp.fp.Flip(fp.fp.GetPosition(), False)

            new_position = rotate_around_point(ref_fp_pos, point_of_rotation, delta_index * delta_angle)
            new_position = [int(x) for x in new_position]
            fp.fp.SetPosition(pcbnew.wxPoint(*new_position))
            footprint_angle = ref_fp.fp.GetOrientationDegrees()-delta_index*delta_angle
            footprint_angle = footprint_angle + index // step * rotation
            fp.fp.SetOrientationDegrees(footprint_angle)

            if copy_text_items:
                self.replicate_fp_text_items(ref_fp, fp)

    def place_linear(self, footprints_to_place, reference_footprint, step_x, step_y, step, rotation, copy_text_items):
        logger.info("Starting placing with linear layout")
        # get proper footprint list
        footprints = []
        for fp in footprints_to_place:
            footprints.append(self.get_fp_by_ref(fp))

        ref_fp = self.get_fp_by_ref(reference_footprint)

        # get reference footprint position
        ref_fp_pos = ref_fp.fp.GetPosition()
        ref_fp_index = footprints.index(ref_fp)

        for fp in footprints:
            index = footprints.index(fp)
            delta_index = index-ref_fp_index

            if fp.fp.IsFlipped() != ref_fp.fp.IsFlipped():
                fp.fp.Flip(fp.fp.GetPosition(), False)

            new_position = (ref_fp_pos.x + delta_index*step_x*SCALE, ref_fp_pos.y + delta_index*step_y * SCALE)
            new_position = [int(x) for x in new_position]
            fp.fp.SetPosition(pcbnew.wxPoint(*new_position))
            footprint_angle = ref_fp.fp.GetOrientationDegrees()
            footprint_angle = footprint_angle + index // step * rotation
            fp.fp.SetOrientationDegrees(footprint_angle)

            if copy_text_items:
                self.replicate_fp_text_items(ref_fp, fp)

    def place_matrix(self, footprints_to_place, reference_footprint, step_x, step_y, nr_columns, step, rotation,
                     copy_text_items):
        logger.info("Starting placing with matrix layout")
        # get proper footprint list
        footprints = []
        for fp in footprints_to_place:
            footprints.append(self.get_fp_by_ref(fp))

        ref_fp = self.get_fp_by_ref(reference_footprint)

        # get first footprint position
        # TODO - take reference footprint position for start and build matrix around it (before, after)
        # TODO - would have to split the for loop into two for loops
        first_fp = footprints[0]
        first_fp_pos = first_fp.fp.GetPosition()

        if copy_text_items:
            self.replicate_fp_text_items(ref_fp, first_fp)

        for fp in footprints[1:]:
            if fp.fp.IsFlipped() != first_fp.fp.IsFlipped():
                fp.fp.Flip(fp.fp.GetPosition(), False)

            index = footprints.index(fp)
            row = index // nr_columns
            column = index - row * nr_columns
            new_pos_x = first_fp_pos.x + column * step_x * SCALE
            new_pos_y = first_fp_pos.y + row * step_y * SCALE
            new_position = (new_pos_x, new_pos_y)
            new_position = [int(x) for x in new_position]
            fp.fp.SetPosition(pcbnew.wxPoint(*new_position))
            footprint_angle = ref_fp.fp.GetOrientationDegrees()
            footprint_angle = footprint_angle + index // step * rotation
            fp.fp.SetOrientationDegrees(footprint_angle)

            if copy_text_items:
                self.replicate_fp_text_items(ref_fp, fp)

    def replicate_fp_text_items(self, src_fp, dst_fp):
        dst_anchor_fp_position = dst_fp.fp.GetPosition()
        angle = src_fp.fp.GetOrientationDegrees() - dst_fp.fp.GetOrientationDegrees()

        delta_pos = dst_anchor_fp_position - src_fp.fp.GetPosition()

        src_fp_text_items = self.get_module_text_items(src_fp)
        dst_fp_text_items = self.get_module_text_items(dst_fp)
        # check if both modules (source and the one for replication) have the same number of text items
        if len(src_fp_text_items) != len(dst_fp_text_items):
            raise LookupError(
                "Source module: " + src_fp + " has different number of text items (" + repr(len(src_fp_text_items))
                + ")\nthan module for replication: " + dst_fp.ref + " (" + repr(len(dst_fp_text_items)) + ")")
        # replicate each text item
        for src_text in src_fp_text_items:
            if src_text.IsKeepUpright() and angle != 0.0:
                logger.info("Text of: " + src_fp.ref +
                            " has property \"Keep upright\" rotation might not look as intended")

            index = src_fp_text_items.index(src_text)
            src_text_position = src_text.GetPosition() + delta_pos

            new_position = rotate_around_point(src_text_position, dst_anchor_fp_position, angle)

            # convert to tuple of integers
            new_position = [int(x) for x in new_position]
            dst_fp_text_items[index].SetPosition(pcbnew.wxPoint(*new_position))

            # set layer
            dst_fp_text_items[index].SetLayer(src_text.GetLayer())
            # set orientation
            dst_fp_text_items[index].SetTextAngle(src_text.GetTextAngle())
            # thickness
            dst_fp_text_items[index].SetTextThickness(src_text.GetTextThickness())
            # width
            dst_fp_text_items[index].SetTextWidth(src_text.GetTextWidth())
            # height
            dst_fp_text_items[index].SetTextHeight(src_text.GetTextHeight())
            # rest of the parameters
            dst_fp_text_items[index].SetItalic(src_text.IsItalic())
            dst_fp_text_items[index].SetBold(src_text.IsBold())
            dst_fp_text_items[index].SetMirrored(src_text.IsMirrored())
            dst_fp_text_items[index].SetMultilineAllowed(src_text.IsMultilineAllowed())
            dst_fp_text_items[index].SetHorizJustify(src_text.GetHorizJustify())
            dst_fp_text_items[index].SetVertJustify(src_text.GetVertJustify())
            dst_fp_text_items[index].SetKeepUpright(src_text.IsKeepUpright())
            # set visibility
            dst_fp_text_items[index].SetVisible(src_text.IsVisible())

    @staticmethod
    def get_module_text_items(footprint):
        """ get all text item belonging to a modules """
        list_of_items = [footprint.fp.Reference(), footprint.fp.Value()]

        footprint_items = footprint.fp.GraphicalItems()
        for item in footprint_items:
            if type(item) is pcbnew.FP_TEXT:
                list_of_items.append(item)
        return list_of_items

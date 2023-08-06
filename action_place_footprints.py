# -*- coding: utf-8 -*-
#  action_place_footprints.py
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

import wx
import pcbnew
import os
import logging
import sys
import math
from .initial_dialog_GUI import InitialDialogGUI
from .place_by_reference_GUI import PlaceByReferenceGUI
from .place_by_sheet_GUI import PlaceBySheetGUI
from .error_dialog_GUI import ErrorDialogGUI
from .place_footprints import Placer
import re
import configparser


def fp_set_highlight(fp):
    pads_list = fp.Pads()
    for pad in pads_list:
        pad.SetBrightened()
    drawings = fp.GraphicalItems()
    for item in drawings:
        item.SetBrightened()


def fp_clear_highlight(fp):
    pads_list = fp.Pads()
    for pad in pads_list:
        pad.ClearBrightened()
    drawings = fp.GraphicalItems()
    for item in drawings:
        item.ClearBrightened()


def natural_sort(list_of_strings):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(list_of_strings, key=alphanum_key)


class ErrorDialog(ErrorDialogGUI):
    def SetSizeHints(self, sz1, sz2):
        # DO NOTHING
        pass

    def __init__(self, parent):
        super(ErrorDialog, self).__init__(parent)


class PlaceBySheetDialog(PlaceBySheetGUI):
    def SetSizeHints(self, sz1, sz2):
        # DO NOTHING
        pass

    def __init__(self, parent, placer, ref_fp, user_units):

        super(PlaceBySheetDialog, self).__init__(parent)

        self.placer = placer
        self.user_units = user_units
        self.ref_fp = ref_fp
        self.ref_list = []
        self.list_sheetsChoices = None
        self.config_filename = os.path.join(self.placer.project_folder, 'place_footprints.ini')
        self.logger = logging.getLogger(__name__)

        footprints = self.placer.get_footprints_on_sheet(self.ref_fp.sheet_id)
        self.height, self.width = self.placer.get_footprints_bounding_box_size(footprints)

        self.list_levels.Clear()
        self.list_levels.AppendItems(self.ref_fp.filename)
        # by default select all items
        self.logger.info("Selecting: " + repr(self.list_levels.GetCount()))
        for i in range(self.list_levels.GetCount()):
            self.list_levels.SetSelection(i)

        if user_units == 'mm':
            self.lbl_x_mag.SetLabelText(u"step x (mm):")
            self.lbl_y_angle.SetLabelText(u"step y (mm):")
        else:
            self.lbl_x_mag.SetLabelText(u"step x (mils):")
            self.lbl_y_angle.SetLabelText(u"step y (mils):")
        self.lbl_columns_rad_step.Disable()
        self.val_columns_rad_step.Disable()

        # load config file if it exists
        if os.path.exists(self.config_filename):
            config = configparser.ConfigParser()
            config.read(self.config_filename)
            # if there is by sheet config
            if 'sheet' in config.sections():
                # get the arrangement
                arrangement = config['sheet']['arrangement']
                if arrangement == 'Linear':
                    self.com_arr.SetSelection(0)
                    self.modify_dialog_for_linear()
                    self.val_x_mag.SetValue(config['sheet.linear']['step_x'])
                    self.val_y_angle.SetValue(config['sheet.linear']['step_y'])
                    self.val_nth.SetValue(config['sheet.linear']['nth_rotate'])
                    self.val_rotate.SetValue(config['sheet.linear']['nth_rotate_angle'])
                if arrangement == 'Circular':
                    self.com_arr.SetSelection(2)
                    self.modify_dialog_for_circular()
                    self.val_y_angle.SetValue(config['sheet.circular']['angle'])
                    self.val_columns_rad_step.SetValue(config['sheet.circular']['radial_step'])
                    self.val_x_mag.SetValue(config['sheet.circular']['radius'])
                    self.val_nth.SetValue(config['sheet.circular']['nth_rotate'])
                    self.val_rotate.SetValue(config['sheet.circular']['nth_rotate_angle'])
                if arrangement == 'Matrix':
                    self.com_arr.SetSelection(1)
                    self.modify_dialog_for_matrix()
                    self.val_x_mag.SetValue(config['sheet.matrix']['step_x'])
                    self.val_y_angle.SetValue(config['sheet.matrix']['step_y'])
                    self.val_columns_rad_step.SetValue(config['sheet.matrix']['columns'])
                    self.val_nth.SetValue(config['sheet.matrix']['nth_rotate'])
                    self.val_rotate.SetValue(config['sheet.matrix']['nth_rotate_angle'])

    def on_ok(self, event):
        # test if all entries have numbers, if they don't then don't do anything
        if self.val_x_mag.GetValue() == '':
            return
        if self.val_y_angle.GetValue() == '':
            return
        if self.val_nth.GetValue() == '':
            return
        if self.val_rotate.GetValue() == '':
            return
        if self.com_arr.GetStringSelection() != 'Linear' and self.val_columns_rad_step.GetValue() == '':
            return

        # clear highlights
        for ref in self.ref_list:
            fp = self.placer.get_fp_by_ref(ref).fp
            fp_clear_highlight(fp)

        self.logger.info("Saving config sheet")

        # save the config
        # if existing, append
        if os.path.exists(self.config_filename):
            config = configparser.ConfigParser()
            config.read(self.config_filename)
        else:
            config = configparser.ConfigParser()
        config['sheet'] = {'arrangement': self.com_arr.GetStringSelection()}
        arrangement = config['sheet']['arrangement']
        if arrangement == 'Linear':
            self.logger.info("Saving config sheet linear")
            config['sheet.linear'] = {'step_x': self.val_x_mag.GetValue(),
                                      'step_y': self.val_y_angle.GetValue(),
                                      'nth_rotate': self.val_nth.GetValue(),
                                      'nth_rotate_angle': self.val_rotate.GetValue()}
        if arrangement == 'Circular':
            self.logger.info("Saving config sheet circular")
            config['sheet.circular'] = {'angle': self.val_y_angle.GetValue(),
                                        'radial_step': self.val_columns_rad_step.GetValue(),
                                        'radius': self.val_x_mag.GetValue(),
                                        'nth_rotate': self.val_nth.GetValue(),
                                        'nth_rotate_angle': self.val_rotate.GetValue()}
        if arrangement == 'Matrix':
            self.logger.info("Saving config sheet matrix")
            config['sheet.matrix'] = {'step_x': self.val_x_mag.GetValue(),
                                      'step_y': self.val_y_angle.GetValue(),
                                      'columns': self.val_columns_rad_step.GetValue(),
                                      'nth_rotate': self.val_nth.GetValue(),
                                      'nth_rotate_angle': self.val_rotate.GetValue()}
        with open(self.config_filename, 'w') as configfile:
            self.logger.info("Saving config saving file")
            config.write(configfile)
        event.Skip()

    def modify_dialog_for_linear(self):
        if self.user_units == 'mm':
            self.lbl_x_mag.SetLabelText(u"step x (mm):")
            self.lbl_y_angle.SetLabelText(u"step y (mm):")
            self.val_x_mag.SetValue("%.3f" % self.width)
            self.val_y_angle.SetValue("%.3f" % self.height)
        else:
            self.lbl_x_mag.SetLabelText(u"step x (mils):")
            self.lbl_y_angle.SetLabelText(u"step y (mils):")
            self.val_x_mag.SetValue("%.3f" % (self.width / 25.4))
            self.val_y_angle.SetValue("%.3f" % (self.height / 25.4))
        self.lbl_columns_rad_step.Disable()
        self.val_columns_rad_step.Disable()

    def modify_dialog_for_matrix(self):
        if self.user_units == 'mm':
            self.lbl_x_mag.SetLabelText(u"step x (mm):")
            self.lbl_y_angle.SetLabelText(u"step y (mm):")
            self.val_x_mag.SetValue("%.3f" % self.width)
            self.val_y_angle.SetValue("%.3f" % self.height)
        else:
            self.lbl_x_mag.SetLabelText(u"step x (mils):")
            self.lbl_y_angle.SetLabelText(u"step y (mils):")
            self.val_x_mag.SetValue("%.3f" % (self.width / 25.4))
            self.val_y_angle.SetValue("%.3f" % (self.height / 25.4))
        self.lbl_columns_rad_step.SetLabelText(u"Nr.columns:")
        self.lbl_columns_rad_step.Enable()
        self.val_columns_rad_step.Enable()
        # presume square arrangement,
        # thus the number of columns should be equal to number of rows
        self.val_columns_rad_step.Clear()
        self.val_columns_rad_step.SetValue(str(int(round(math.sqrt(len(self.list_sheets.GetSelections()))))))

    def modify_dialog_for_circular(self):
        number_of_all_sheets = len(self.list_sheets.GetSelections())
        self.logger.info("Selection: " + repr(self.list_sheets.GetSelections()))
        circumference = number_of_all_sheets * self.width
        radius = circumference / (2 * math.pi)
        angle = 360.0 / number_of_all_sheets
        if self.user_units == 'mm':
            self.lbl_x_mag.SetLabelText(u"radius (mm):")
            self.val_x_mag.SetValue("%.3f" % radius)
        else:
            self.lbl_x_mag.SetLabelText(u"radius (mils):")
            self.val_x_mag.SetValue("%.3f" % (radius / 25.4))
        self.lbl_y_angle.SetLabelText(u"angle (deg):")
        self.val_y_angle.SetValue("%.3f" % angle)
        if self.user_units == 'mm':
            self.lbl_columns_rad_step.SetLabelText(u"radial step (mm):")
        else:
            self.lbl_columns_rad_step.SetLabelText(u"radial step (mils):")
        self.lbl_columns_rad_step.Enable()
        self.val_columns_rad_step.SetValue("0.0")
        self.val_columns_rad_step.Enable()

    def level_changed(self, event):
        index = self.list_levels.GetSelection()

        self.list_sheetsChoices = self.placer.get_sheets_to_replicate(self.ref_fp, self.ref_fp.sheet_id[index])

        # clear highlights
        for ref in self.ref_list:
            fp = self.placer.get_fp_by_ref(ref).fp
            fp_clear_highlight(fp)
        pcbnew.Refresh()

        # get footprints with same id
        footprints_with_same_id = self.placer.get_list_of_footprints_with_same_id(self.ref_fp.fp_id)

        # find matching anchors to matching sheets so that indices will match
        self.ref_list = []
        for sheet in self.list_sheetsChoices:
            for fp in footprints_with_same_id:
                if "/".join(sheet) in "/".join(fp.sheet_id):
                    self.ref_list.append(fp.ref)
                    break

        sheets_for_list = ['/'.join(x[0]) + " (" + x[1] + ")" for x in zip(self.list_sheetsChoices, self.ref_list)]

        self.list_sheets.Clear()
        self.list_sheets.AppendItems(sheets_for_list)

        # by default select all sheets
        number_of_items = self.list_sheets.GetCount()
        for i in range(number_of_items):
            self.list_sheets.Select(i)

        # highlight all footprints
        for ref in self.ref_list:
            fp = self.placer.get_fp_by_ref(ref).fp
            fp_set_highlight(fp)
        pcbnew.Refresh()

        if self.com_arr.GetStringSelection() == u"Linear":
            self.modify_dialog_for_linear()
        if self.com_arr.GetStringSelection() == u"Matrix":
            self.modify_dialog_for_matrix()
        if self.com_arr.GetStringSelection() == u"Circular":
            self.modify_dialog_for_circular()

    def on_selected(self, event):
        # go through the list and set/clear highlight accordingly
        nr_items = self.list_sheets.GetCount()
        for i in range(nr_items):
            fp_ref = self.ref_list[i]
            fp = self.placer.get_fp_by_ref(fp_ref).fp
            if self.list_sheets.IsSelected(i):
                fp_set_highlight(fp)
            else:
                fp_clear_highlight(fp)
        pcbnew.Refresh()

    def arr_changed(self, event):
        if self.com_arr.GetStringSelection() == u"Linear":
            self.modify_dialog_for_linear()
        if self.com_arr.GetStringSelection() == u"Matrix":
            self.modify_dialog_for_matrix()
        if self.com_arr.GetStringSelection() == u"Circular":
            self.modify_dialog_for_circular()
        event.Skip()


class PlaceByReferenceDialog(PlaceByReferenceGUI):
    # hack for new wxFormBuilder generating code incompatible with old wxPython
    # noinspection PyMethodOverriding
    def SetSizeHints(self, sz1, sz2):
        # DO NOTHING
        pass

    def __init__(self, parent, placer, ref_fp, user_units):
        super(PlaceByReferenceDialog, self).__init__(parent)

        self.placer = placer
        self.user_units = user_units
        self.config_filename = os.path.join(self.placer.project_folder, 'place_footprints.ini')
        self.logger = logging.getLogger(__name__)

        # grab footprint data
        self.ref_fp = ref_fp
        self.height, self.width = self.placer.get_footprints_bounding_box_size([self.ref_fp])

        # populate default values
        if self.user_units == 'mm':
            self.lbl_x_mag.SetLabelText(u"step x (mm):")
            self.lbl_y_angle.SetLabelText(u"step y (mm):")
        else:
            self.lbl_x_mag.SetLabelText(u"step x (mils):")
            self.lbl_y_angle.SetLabelText(u"step y (mils):")
        self.lbl_columns_rad_step.Disable()
        self.val_columns_rad_step.Disable()

        # load config file if it
    def on_show( self, event ):
        if os.path.exists(self.config_filename):
            config = configparser.ConfigParser()
            config.read(self.config_filename)
            # if there is by sheet config
            if 'reference' in config.sections():
                # get the arrangement
                arrangement = config['reference']['arrangement']
                if arrangement == 'Linear':
                    self.com_arr.SetSelection(0)
                    self.modify_dialog_for_linear()
                    self.val_x_mag.SetValue(config['reference.linear']['step_x'])
                    self.val_y_angle.SetValue(config['reference.linear']['step_y'])
                    self.val_nth.SetValue(config['reference.linear']['nth_rotate'])
                    self.val_rotate.SetValue(config['reference.linear']['nth_rotate_angle'])
                if arrangement == 'Circular':
                    self.com_arr.SetSelection(2)
                    self.modify_dialog_for_circular()
                    self.val_y_angle.SetValue(config['reference.circular']['angle'])
                    self.val_columns_rad_step.SetValue(config['reference.circular']['radial_step'])
                    self.val_x_mag.SetValue(config['reference.circular']['radius'])
                    self.val_nth.SetValue(config['reference.circular']['nth_rotate'])
                    self.val_rotate.SetValue(config['reference.circular']['nth_rotate_angle'])
                if arrangement == 'Matrix':
                    self.com_arr.SetSelection(1)
                    self.modify_dialog_for_matrix()
                    self.val_x_mag.SetValue(config['reference.matrix']['step_x'])
                    self.val_y_angle.SetValue(config['reference.matrix']['step_y'])
                    self.val_columns_rad_step.SetValue(config['reference.matrix']['columns'])
                    self.val_nth.SetValue(config['reference.matrix']['nth_rotate'])
                    self.val_rotate.SetValue(config['reference.matrix']['nth_rotate_angle'])
        event.Skip()

    def arr_changed(self, event):
        # linear layout
        if self.com_arr.GetStringSelection() == u"Linear":
            self.modify_dialog_for_linear()
        # Matrix
        if self.com_arr.GetStringSelection() == u"Matrix":
            self.modify_dialog_for_matrix()
        # circular layout
        if self.com_arr.GetStringSelection() == u"Circular":
            self.modify_dialog_for_circular()

        event.Skip()

    def modify_dialog_for_linear(self):
        if self.user_units == 'mm':
            self.lbl_x_mag.SetLabelText(u"step x (mm):")
            self.lbl_y_angle.SetLabelText(u"step y (mm):")
            self.val_x_mag.SetValue("%.3f" % self.width)
            self.val_y_angle.SetValue("%.3f" % self.height)
        else:
            self.lbl_x_mag.SetLabelText(u"step x (mils):")
            self.lbl_y_angle.SetLabelText(u"step y (mils):")
            self.val_x_mag.SetValue("%.3f" % (self.width / 25.4))
            self.val_y_angle.SetValue("%.3f" % (self.height / 25.4))
        self.lbl_columns_rad_step.Disable()
        self.val_columns_rad_step.Disable()

    def modify_dialog_for_circular(self):
        number_of_all_footprints = len(self.list_footprints.GetSelections())
        circumference = number_of_all_footprints * self.width
        radius = circumference / (2 * math.pi)
        angle = 360.0 / number_of_all_footprints
        if self.user_units == 'mm':
            self.lbl_x_mag.SetLabelText(u"radius (mm):")
            self.val_x_mag.SetValue("%.3f" % radius)
        else:
            self.lbl_x_mag.SetLabelText(u"radius (mils):")
            self.val_x_mag.SetValue("%.3f" % (radius / 25.4))
        self.lbl_y_angle.SetLabelText(u"angle (deg):")
        self.val_y_angle.SetValue("%.3f" % angle)
        if self.user_units == 'mm':
            self.lbl_columns_rad_step.SetLabelText(u"radial step (mm):")
        else:
            self.lbl_columns_rad_step.SetLabelText(u"radial step (mils):")
        self.lbl_columns_rad_step.Enable()
        self.val_columns_rad_step.SetValue("0.0")
        self.val_columns_rad_step.Enable()

    def modify_dialog_for_matrix(self):
        if self.user_units == 'mm':
            self.lbl_x_mag.SetLabelText(u"step x (mm):")
            self.lbl_y_angle.SetLabelText(u"step y (mm):")
            self.val_x_mag.SetValue("%.3f" % self.width)
            self.val_y_angle.SetValue("%.3f" % self.height)
        else:
            self.lbl_x_mag.SetLabelText(u"step x (mils):")
            self.lbl_y_angle.SetLabelText(u"step y (mils):")
            self.val_x_mag.SetValue("%.3f" % (self.width / 25.4))
            self.val_y_angle.SetValue("%.3f" % (self.height / 25.4))
        self.lbl_columns_rad_step.SetLabelText(u"Nr.columns:")
        self.lbl_columns_rad_step.Enable()
        self.val_columns_rad_step.Enable()
        self.val_columns_rad_step.Clear()
        self.val_columns_rad_step.SetValue(str(int(round(math.sqrt(len(self.list_footprints.GetSelections()))))))

    def on_selected(self, event):
        # go through the list and set/clear highlight accordingly
        nr_items = self.list_footprints.GetCount()
        for i in range(nr_items):
            fp_ref = self.list_footprints.GetString(i)
            fp = self.placer.get_fp_by_ref(fp_ref)
            footprint = fp.fp
            if self.list_footprints.IsSelected(i):
                fp_set_highlight(footprint)
            else:
                fp_clear_highlight(footprint)
        pcbnew.Refresh()

    def on_ok(self, event):
        if self.val_x_mag.GetValue() == '':
            return
        if self.val_y_angle.GetValue() == '':
            return
        if self.val_nth.GetValue() == '':
            return
        if self.val_rotate.GetValue() == '':
            return
        if self.com_arr.GetStringSelection() != 'Linear' and self.val_columns_rad_step.GetValue() == '':
            return

        # clear highlights
        # TODO
        # save the config
        # if existing, append
        if os.path.exists(self.config_filename):
            config = configparser.ConfigParser()
            config.read(self.config_filename)
        else:
            config = configparser.ConfigParser()
        config['reference'] = {'arrangement': self.com_arr.GetStringSelection()}
        arrangement = config['reference']['arrangement']
        if arrangement == 'Linear':
            config['reference.linear'] = {'step_x': self.val_x_mag.GetValue(),
                                          'step_y': self.val_y_angle.GetValue(),
                                          'nth_rotate': self.val_nth.GetValue(),
                                          'nth_rotate_angle':  self.val_rotate.GetValue()}
        if arrangement == 'Circular':
            config['reference.circular'] = {'angle': self.val_y_angle.GetValue(),
                                            'radial_step': self.val_columns_rad_step.GetValue(),
                                            'radius': self.val_x_mag.GetValue(),
                                            'nth_rotate': self.val_nth.GetValue(),
                                            'nth_rotate_angle': self.val_rotate.GetValue()}
        if arrangement == 'Matrix':
            config['reference.matrix'] = {'step_x': self.val_x_mag.GetValue(),
                                          'step_y': self.val_y_angle.GetValue(),
                                          'columns': self.val_columns_rad_step.GetValue(),
                                          'nth_rotate': self.val_nth.GetValue(),
                                          'nth_rotate_angle': self.val_rotate.GetValue()}
        with open(self.config_filename, 'w') as configfile:
            config.write(configfile)

        event.Skip()


class InitialDialog(InitialDialogGUI):
    BY_REFERENCE = 1025
    BY_SHEET = 1026

    # hack for new wxFormBuilder generating code incompatible with old wxPython
    # noinspection PyMethodOverriding
    def SetSizeHints(self, sz1, sz2):
        # DO NOTHING
        pass

    def __init__(self, parent):
        super(InitialDialog, self).__init__(parent)

    def on_by_reference(self, event):
        event.Skip()
        self.EndModal(InitialDialog.BY_REFERENCE)

    def on_by_sheet(self, event):
        event.Skip()
        self.EndModal(InitialDialog.BY_SHEET)


class PlaceFootprints(pcbnew.ActionPlugin):
    """
    A plugin to place selected footprints or footprints from multiple sheets
    in linear, circular or matrix arrangement
    """

    def __init__(self):
        super(PlaceFootprints, self).__init__()

        self.frame = None

        self.name = "Place Footprints"
        self.category = "Place Footprints"
        self.description = "place selected footprints or footprints from multiple sheets " \
                           "in linear, circular or matrix arrangement"
        self.icon_file_name = os.path.join(
            os.path.dirname(__file__), 'place_footprints_light.png')
        self.dark_icon_file_name = os.path.join(
            os.path.dirname(__file__), 'place_footprints_dark.png')

        self.debug_level = logging.INFO

        # plugin paths
        self.plugin_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        self.version_file_path = os.path.join(self.plugin_folder, 'version.txt')

        # load the plugin version
        with open(self.version_file_path) as fp:
            self.version = fp.readline()

    def defaults(self):
        pass

    def Run(self):
        # grab PCB editor frame
        self.frame = wx.FindWindowByName("PcbFrame")

        # load board
        board = pcbnew.GetBoard()

        # find the user units
        if pcbnew.GetUserUnits() == 1:
            user_units = 'mm'
        else:
            user_units = 'in'

        # go to the project folder - so that log will be in proper place
        os.chdir(os.path.dirname(os.path.abspath(board.GetFileName())))

        # Remove all handlers associated with the root logger object.
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        file_handler = logging.FileHandler(filename='place_footprints.log', mode='w')
        handlers = [file_handler]

        # set up logger
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(name)s %(lineno)d:%(message)s',
                            datefmt='%m-%d %H:%M:%S',
                            handlers=handlers)
        logger = logging.getLogger(__name__)
        logger.info("Plugin executed on: " + repr(sys.platform))
        logger.info("Plugin executed with python version: " + repr(sys.version))
        logger.info("KiCad build version: " + str(pcbnew.GetBuildVersion()))
        logger.info("Plugin version: " + self.version)
        logger.info("Frame repr: " + repr(self.frame))

        # check if there is exactly one footprints selected
        selected_footprints = [x.GetReference() for x in board.GetFootprints() if x.IsSelected()]

        # if more or less than one show only a message box
        if len(selected_footprints) != 1:
            caption = 'Place footprints'
            message = "More or less than 1 footprint selected. Please select exactly one footprint " \
                      "and run the script again"
            dlg = wx.MessageDialog(self.frame, message, caption, wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return

        # this is the reference footprint reference
        ref_fp_ref = selected_footprints[0]

        # instance a placer to get board info
        try:
            placer = Placer(board)
        except LookupError as error:
            caption = 'Place footprints'
            message = str(error)
            dlg = wx.MessageDialog(self.frame, message, caption, wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            logging.shutdown()
            return
        except Exception as error:
            logger.exception("Fatal error when executing Place Footprints plugin")
            e_dlg = ErrorDialog(self.frame)
            e_dlg.ShowModal()
            e_dlg.Destroy()
            logging.shutdown()
            return

        # get reference footprint
        ref_fp = placer.get_fp_by_ref(ref_fp_ref)

        # ask user which way to select other footprints (by increasing reference number or by ID)
        dlg_initial = InitialDialog(self.frame)
        dlg_initial.btn_sheet.SetDefault()
        dlg_initial.CenterOnParent()
        ret_initial = dlg_initial.ShowModal()
        dlg_initial.Destroy()

        if ret_initial == InitialDialog.BY_SHEET:
            # get list of all footprints with same ID
            footprints_with_same_id = placer.get_list_of_footprints_with_same_id(ref_fp.fp_id)
            # display dialog
            dlg = PlaceBySheetDialog(self.frame, placer, ref_fp, user_units)

            # show the dialog
            dlg.CenterOnParent()
            res = dlg.ShowModal()

            if res == wx.ID_CANCEL:
                # clear highlight on all footprints by default
                for fp in footprints_with_same_id:
                    fp_clear_highlight(fp.fp)
                pcbnew.Refresh()
                return

            # get the sheet_id's selected for placement
            sheets_to_place_indices = dlg.list_sheets.GetSelections()
            sheets_to_place = [dlg.list_sheetsChoices[i] for i in sheets_to_place_indices]
            logger.info("Sheets selected: " + repr(sheets_to_place))

            fp_references = [ref_fp_ref]
            for sheet in sheets_to_place:
                for fp in footprints_with_same_id:
                    if "/".join(sheet) in "/".join(fp.sheet_id):
                        fp_references.append(fp.ref)
                        break

            logger.info("Footprints to place: " + repr(fp_references))
            # sort by reference number
            sorted_footprints = natural_sort(fp_references)

            # get mode
            if dlg.com_arr.GetStringSelection() == u'Circular':
                delta_angle = float(dlg.val_y_angle.GetValue().replace(",", "."))
                step = int(dlg.val_nth.GetValue())
                rotation = float(dlg.val_rotate.GetValue().replace(",", "."))
                if user_units == 'mm':
                    radius = float(dlg.val_x_mag.GetValue().replace(",", "."))
                    delta_radius = float(dlg.val_columns_rad_step.GetValue().replace(",", "."))
                else:
                    radius = float(dlg.val_x_mag.GetValue().replace(",", ".")) * 25.4
                    delta_radius = float(dlg.val_columns_rad_step.GetValue().replace(",", ".")) * 25.4
                try:
                    placer.place_circular(sorted_footprints, ref_fp_ref, radius, delta_angle, delta_radius,
                                          step, rotation, True)
                    logger.info("Placing complete")
                    logging.shutdown()
                except Exception:
                    logger.exception("Fatal error when executing place footprints")
                    e_dlg = ErrorDialog(self.frame)
                    e_dlg.ShowModal()
                    e_dlg.Destroy()
                    logging.shutdown()

                    # clear highlight all footprints by default
                    for fp_ref in sorted_footprints:
                        fp = placer.get_fp_by_ref(fp_ref).fp
                        fp_clear_highlight(fp)
                    pcbnew.Refresh()
                    return

            if dlg.com_arr.GetStringSelection() == u'Linear':
                step = int(dlg.val_nth.GetValue())
                rotation = float(dlg.val_rotate.GetValue().replace(",", "."))
                if user_units == 'mm':
                    step_x = float(dlg.val_x_mag.GetValue().replace(",", "."))
                    step_y = float(dlg.val_y_angle.GetValue().replace(",", "."))
                else:
                    step_x = float(dlg.val_x_mag.GetValue().replace(",", ".")) * 25.4
                    step_y = float(dlg.val_y_angle.GetValue().replace(",", ".")) * 25.4
                try:
                    placer.place_linear(sorted_footprints, ref_fp_ref, step_x, step_y, step, rotation, True)
                    logger.info("Placing complete")
                    logger.info("Sorted_footprints: " + repr(sorted_footprints))
                    logging.shutdown()
                except Exception:
                    logger.exception("Fatal error when executing place footprints")
                    e_dlg = ErrorDialog(self.frame)
                    e_dlg.ShowModal()
                    e_dlg.Destroy()
                    logging.shutdown()
                    # clear highlight all footprints by default
                    for fp_ref in sorted_footprints:
                        fp = placer.get_fp_by_ref(fp_ref).fp
                        fp_clear_highlight(fp)
                    pcbnew.Refresh()
                    return

            if dlg.com_arr.GetStringSelection() == u'Matrix':
                step = int(dlg.val_nth.GetValue())
                rotation = float(dlg.val_rotate.GetValue().replace(",", "."))
                if user_units == 'mm':
                    step_x = float(dlg.val_x_mag.GetValue().replace(",", "."))
                    step_y = float(dlg.val_y_angle.GetValue().replace(",", "."))
                else:
                    step_x = float(dlg.val_x_mag.GetValue().replace(",", ".")) * 25.4
                    step_y = float(dlg.val_y_angle.GetValue().replace(",", ".")) * 25.4
                nr_columns = int(dlg.val_columns_rad_step.GetValue().replace(",", "."))
                try:
                    placer.place_matrix(sorted_footprints, ref_fp_ref, step_x, step_y, nr_columns, step, rotation, True)
                    logger.info("Placing complete")
                    logging.shutdown()
                except Exception:
                    logger.exception("Fatal error when executing place footprints")
                    e_dlg = ErrorDialog(self.frame)
                    e_dlg.ShowModal()
                    e_dlg.Destroy()
                    logging.shutdown()
                    # clear highlight all footprints by default
                    for fp_ref in sorted_footprints:
                        fp = placer.get_fp_by_ref(fp_ref).fp
                        fp_clear_highlight(fp)
                    pcbnew.Refresh()
                    return

            # clear highlight all footprints by default
            for fp_ref in sorted_footprints:
                fp = placer.get_fp_by_ref(fp_ref).fp
                fp_clear_highlight(fp)
            dlg.Destroy()
            pcbnew.Refresh()

        if ret_initial == InitialDialog.BY_REFERENCE:
            # split the reference footprint reference into designator and number
            index = 0
            for i in range(len(ref_fp_ref)):
                if not ref_fp_ref[i].isdigit():
                    index = i + 1
            fp_ref_designator = ref_fp_ref[:index]
            fp_ref_number = ref_fp_ref[index:]
            logger.info("Reference designator is: " + fp_ref_designator)
            logger.info("Reference number is: " + fp_ref_number)

            # get list of all footprints with same reference designator
            list_of_all_footprints_with_same_designator = placer.get_footprints_with_reference_designator(
                fp_ref_designator)

            sorted_list = sorted(list_of_all_footprints_with_same_designator, key=lambda x: int(x[index:]))

            # find only consecutive footprints
            list_of_consecutive_footprints = []
            # go through the list in positive direction
            start_index = sorted_list.index(ref_fp_ref)
            count_start = int(fp_ref_number)
            for fp_ref in sorted_list[start_index:]:
                if int(fp_ref[index:]) == count_start:
                    count_start = count_start + 1
                    list_of_consecutive_footprints.append(fp_ref)
                else:
                    break

            # go through the list in negative direction
            reversed_list = list(reversed(sorted_list))
            start_index = reversed_list.index(ref_fp_ref)
            count_start = int(fp_ref_number)
            for fp_ref in reversed_list[start_index:]:
                if int(fp_ref[index:]) == count_start:
                    count_start = count_start - 1
                    list_of_consecutive_footprints.append(fp_ref)
                else:
                    break

            sorted_footprints = natural_sort(list(set(list_of_consecutive_footprints)))
            logger.info('Sorted and filtered list:\n' + repr(sorted_footprints))

            # create dialog
            dlg = PlaceByReferenceDialog(self.frame, placer, ref_fp, user_units)
            
            dlg.list_footprints.AppendItems(sorted_footprints)

            # by default select all footprints on the list
            number_of_items = dlg.list_footprints.GetCount()
            for i in range(number_of_items):
                dlg.list_footprints.Select(i)

            # highlight all footprints by default
            for fp_ref in sorted_footprints:
                fp = placer.get_fp_by_ref(fp_ref).fp
                fp_set_highlight(fp)
            pcbnew.Refresh()

            # show dialog
            dlg.CenterOnParent()
            res = dlg.ShowModal()

            if res == wx.ID_CANCEL:
                dlg.Destroy()
                # clear highlight all footprints by default
                for fp_ref in sorted_footprints:
                    fp = placer.get_fp_by_ref(fp_ref).fp
                    fp_clear_highlight(fp)
                pcbnew.Refresh()
                logging.shutdown()
                return

            # get copy_text_items_checkbox
            copy_text_items = dlg.cb_positions.IsChecked()

            # get list of footprints to place
            footprints_to_place_indices = dlg.list_footprints.GetSelections()
            footprints_to_place = natural_sort([sorted_footprints[i] for i in footprints_to_place_indices])
            logger.info('Footprints to place:\n' + repr(footprints_to_place))
            # get mode
            if dlg.com_arr.GetStringSelection() == u'Circular':
                delta_angle = float(dlg.val_y_angle.GetValue().replace(",", "."))
                step = int(dlg.val_nth.GetValue())
                rotation = float(dlg.val_rotate.GetValue().replace(",", "."))
                if user_units == 'mm':
                    radius = float(dlg.val_x_mag.GetValue().replace(",", "."))
                    delta_radius = float(dlg.val_columns_rad_step.GetValue().replace(",", "."))
                else:
                    radius = float(dlg.val_x_mag.GetValue().replace(",", ".")) * 25.4
                    delta_radius = float(dlg.val_columns_rad_step.GetValue().replace(",", ".")) * 25.4
                try:
                    placer.place_circular(footprints_to_place, ref_fp_ref, radius, delta_angle, delta_radius,
                                          step, rotation, copy_text_items)
                    logger.info("Placing complete")
                    logging.shutdown()
                except Exception:
                    logger.exception("Fatal error when executing place footprints")
                    e_dlg = ErrorDialog(self.frame)
                    e_dlg.ShowModal()
                    e_dlg.Destroy()()
                    # clear highlight all footprints by default
                    for fp_ref in sorted_footprints:
                        fp = placer.get_fp_by_ref(fp_ref).fp
                        fp_clear_highlight(fp)
                    pcbnew.Refresh()
                    return

            if dlg.com_arr.GetStringSelection() == u'Linear':
                step = int(dlg.val_nth.GetValue())
                rotation = float(dlg.val_rotate.GetValue().replace(",", "."))
                if user_units == 'mm':
                    step_x = float(dlg.val_x_mag.GetValue().replace(",", "."))
                    step_y = float(dlg.val_y_angle.GetValue().replace(",", "."))
                else:
                    step_x = float(dlg.val_x_mag.GetValue().replace(",", ".")) * 25.4
                    step_y = float(dlg.val_y_angle.GetValue().replace(",", ".")) * 25.4
                try:
                    placer.place_linear(footprints_to_place, ref_fp_ref, step_x, step_y, step, rotation,
                                        copy_text_items)
                    logger.info("Placing complete")
                    logging.shutdown()
                except Exception:
                    logger.exception("Fatal error when executing place footprints")
                    e_dlg = ErrorDialog(self.frame)
                    e_dlg.ShowModal()
                    e_dlg.Destroy()
                    logging.shutdown()
                    # clear highlight all footprints by default
                    for fp_ref in sorted_footprints:
                        fp = placer.get_fp_by_ref(fp_ref).fp
                        fp_clear_highlight(fp)
                    pcbnew.Refresh()
                    dlg_initial.Destroy()
                    return

            if dlg.com_arr.GetStringSelection() == u'Matrix':
                step = int(dlg.val_nth.GetValue())
                rotation = float(dlg.val_rotate.GetValue().replace(",", "."))
                if user_units == 'mm':
                    step_x = float(dlg.val_x_mag.GetValue().replace(",", "."))
                    step_y = float(dlg.val_y_angle.GetValue().replace(",", "."))
                else:
                    step_x = float(dlg.val_x_mag.GetValue().replace(",", ".")) * 25.4
                    step_y = float(dlg.val_y_angle.GetValue().replace(",", ".")) * 25.4
                nr_columns = int(dlg.val_columns_rad_step.GetValue())
                try:
                    placer.place_matrix(footprints_to_place, ref_fp_ref, step_x, step_y, nr_columns, step, rotation,
                                        copy_text_items)
                    logger.info("Placing complete")
                    logging.shutdown()
                except Exception:
                    logger.exception("Fatal error when executing place footprints")
                    e_dlg = ErrorDialog(self.frame)
                    e_dlg.ShowModal()
                    e_dlg.Destroy()
                    logging.shutdown()
                    # clear highlight all footprints by default
                    for fp_ref in sorted_footprints:
                        fp = placer.get_fp_by_ref(fp_ref).fp
                        fp_clear_highlight(fp)
                    pcbnew.Refresh()
                    dlg_initial.Destroy()
                    return

            # clear highlight all footprints by default
            for fp_ref in sorted_footprints:
                fp = placer.get_fp_by_ref(fp_ref).fp
                fp_clear_highlight(fp)
            dlg.Destroy()
            pcbnew.Refresh()

        # clean up before exiting
        logging.shutdown()

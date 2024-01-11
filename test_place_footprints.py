import unittest
import pcbnew
import logging
import sys
import os
from place_footprints import Placer
import compare_boards
import re


def natural_sort(l):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


def test(in_file, out_file, ref_fp_ref, mode, layout):
    board = pcbnew.LoadBoard(in_file)

    placer = Placer(board)

    if mode == 'by ref':
        footprint_reference_designator = ''.join(i for i in ref_fp_ref if not i.isdigit())
        footprint_reference_number = int(''.join(i for i in ref_fp_ref if i.isdigit()))

        # get list of all footprints with same reference designator
        list_of_all_footprints_with_same_designator = placer.get_footprints_with_reference_designator(footprint_reference_designator)
        sorted_list = natural_sort(list_of_all_footprints_with_same_designator)

        list_of_consecutive_footprints=[]
        start_index = sorted_list.index(ref_fp_ref)
        count_start = footprint_reference_number
        for fp in sorted_list[start_index:]:
            if int(''.join(i for i in fp if i.isdigit())) == count_start:
                count_start = count_start + 1
                list_of_consecutive_footprints.append(fp)
            else:
                break

        count_start = footprint_reference_number
        reversed_list = list(reversed(sorted_list))
        start_index = reversed_list.index(ref_fp_ref)
        for fp in reversed_list[start_index:]:
            if int(''.join(i for i in fp if i.isdigit())) == count_start:
                count_start = count_start -1
                list_of_consecutive_footprints.append(fp)
            else:
                break

        sorted_footprints = natural_sort(list(set(list_of_consecutive_footprints)))

    if mode == 'by sheet':
        ref_footprint = placer.get_fp_by_ref(ref_fp_ref)
        list_of_footprints = placer.get_list_of_footprints_with_same_id(ref_footprint.fp_id)
        footprints = []
        for fp in list_of_footprints:
            footprints.append(fp.ref)
        sorted_footprints = natural_sort(footprints)

    if layout == 'circular':
        placer.place_circular(sorted_footprints, ref_fp_ref,
                              radius=10.0, delta_angle=45.0, delta_radius=+1.0, step=1, rotation=0, copy_text_items=True)
    if layout == 'linear':
        placer.place_linear(sorted_footprints, ref_fp_ref,
                            step_x=5.0, step_y=0.0, step=3, rotation=15, copy_text_items=True)
    if layout == 'matrix':
        placer.place_matrix(sorted_footprints, ref_fp_ref,
                            step_x=5.0, step_y=5.0, nr_columns=3, step=3, rotation=15, copy_text_items=True)

    saved = pcbnew.SaveBoard(out_file, board)
    test_file = out_file.replace("temp", "test")

    print("Comparing board files")
    ret_val = compare_boards.compare_boards(out_file, test_file)
    #ret_val = 1
    # remove the temporary board file
    # os.remove(out_file)

    return ret_val


class TestByRef(unittest.TestCase):
    def setUp(self):
        # basic setup
        os.chdir(os.path.join(os.path.dirname(os.path.realpath(__file__)), "place_footprints_test_projects"))
        self.input_file = 'place_footprints.kicad_pcb'
        self.ref_fp_ref = 'R202'

    def test_circular_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_ref_circular" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by ref', 'circular')
        self.assertEqual(err, 0, "Should be 0")

    def test_linear_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_ref_linear" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by ref', 'linear')
        self.assertEqual(err, 0, "Should be 0")

    def test_matrix_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_ref_matrix" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by ref', 'matrix')
        self.assertEqual(err, 0, "Should be 0")


class TestByRefFlipped(unittest.TestCase):
    def setUp(self):
        # basic setup
        os.chdir(os.path.join(os.path.dirname(os.path.realpath(__file__)), "place_footprints_test_projects"))
        self.input_file = 'place_footprints.kicad_pcb'
        self.ref_fp_ref = 'R304'

    def test_circular_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_ref_circular_flipped" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by ref', 'circular')
        self.assertEqual(err, 0, "Should be 0")

    def test_linear_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_ref_linear_flipped" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by ref', 'linear')
        self.assertEqual(err, 0, "Should be 0")

    def test_matrix_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_ref_matrix_flipped" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by ref', 'matrix')
        self.assertEqual(err, 0, "Should be 0")


class TestBySheet(unittest.TestCase):
    def setUp(self):
        # basic setup
        os.chdir(os.path.join(os.path.dirname(os.path.realpath(__file__)), "place_footprints_test_projects"))
        self.input_file = 'place_footprints.kicad_pcb'
        self.ref_fp_ref = 'R401'

    def test_circular_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_sheet_circular" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by sheet', 'circular')
        self.assertEqual(err, 0, "Should be 0")

    def test_linear_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_sheet_linear" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by sheet', 'linear')
        self.assertEqual(err, 0, "Should be 0")

    def test_matrix_by_ref(self):
        output_file = self.input_file.split('.')[0] + "_temp_sheet_matrix" + ".kicad_pcb"
        err = test(self.input_file, output_file, self.ref_fp_ref, 'by sheet', 'matrix')
        self.assertEqual(err, 0, "Should be 0")


if __name__ == '__main__':
    file_handler = logging.FileHandler(filename='place_footprints.log', mode='w')
    stdout_handler = logging.StreamHandler(sys.stdout)
    handlers = [file_handler, stdout_handler]

    logging_level = logging.INFO

    logging.basicConfig(level=logging_level,
                        format='%(asctime)s %(name)s %(lineno)d:%(message)s',
                        datefmt='%m-%d %H:%M:%S',
                        handlers=handlers
                        )

    logger = logging.getLogger(__name__)
    logger.info("Plugin executed on: " + repr(sys.platform))
    logger.info("Plugin executed with python version: " + repr(sys.version))
    logger.info("KiCad build version: " + str(pcbnew.GetBuildVersion()))

    unittest.main()

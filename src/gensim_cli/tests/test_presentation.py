"""
Test all the interfaces with third party services
"""
from unittest import TestCase
import unittest.mock
import sys

from automail.utils import presentation

class TestPresent(TestCase):

    def setUp(self):
        cls = presentation.Present
        # we have to mock print
        self.mock_print = unittest.mock.Mock()
        presentation.print = self.mock_print
        #cls.algo = self.mock_request
        self.mock_instance = cls()

    def tearDown(self):
        pass

    @staticmethod
    def assert_called_with_args(mock, arg):
        flag = False
        for call in mock.call_args_list:
            print(call.args)
            print(arg)
            if arg in call.args:
                flag = True
        assert flag, (arg, mock.call_args_list)

    def test_print_blank_line(self):
        self.mock_instance.print_blank()
        self.assert_called_with_args(self.mock_print, " "*(self.mock_instance.WINDOW_SIZE-2))

    def test_print_line(self):
        self.mock_instance.print_line()
        self.assert_called_with_args(self.mock_print, self.mock_instance.dchara*(self.mock_instance.WINDOW_SIZE))

    def test_print_cmd(self):
        self.mock_instance.print_cmd("", cmds={"blobs": "doko"})
        self.assert_called_with_args(self.mock_print, "[blobs] doko")

import unittest
from unittest.mock import MagicMock, call

from extras.mmu.mmu_extruder_heater import MmuExtruderHeater

class TestMmuExtruderHeater(unittest.TestCase):
    def setUp(self):
        self.extruder_heater = MmuExtruderHeater(MagicMock(), 'extruder')

    def test_get_current_temp_delegates(self):
        self.extruder_heater.extruder.get_status = MagicMock(return_value={'temperature': 123})

        self.assertEqual(123, self.extruder_heater.get_current_temp())

    def test_get_target_temp_delegates(self):
        self.extruder_heater.extruder.heater.target_temp = 234

        self.assertEqual(234, self.extruder_heater.get_target_temp())

    def test_store_target_temp_when_no_temp_stored(self):
        """Check that store_target_temp() stores the current target temp when no temp is stored."""
        self.extruder_heater.extruder.heater.target_temp = 345

        self.extruder_heater.store_target_temp()

        self.assertEqual(345, self.extruder_heater.stored_temp)

    def test_store_target_temp_when_temp_stored(self):
        """Check that store_target_temp() does not overwrite the stored temp."""
        self.extruder_heater.extruder.heater.target_temp = 345
        self.extruder_heater.stored_temp = 456

        self.extruder_heater.store_target_temp()

        self.assertEqual(456, self.extruder_heater.stored_temp)

    def test_reset_stored_temp(self):
        self.extruder_heater.stored_temp = 567

        self.extruder_heater.reset_stored_temp()

        self.assertEqual(-1, self.extruder_heater.stored_temp)

    def test_set_target_temp_runs_gcode(self):
        self.extruder_heater.set_target_temp(678, wait=False)

        self.extruder_heater.gcode.run_script_from_command.assert_called_once_with("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=678.0")

    def test_set_target_temp_runs_wait_gcode(self):
        self.extruder_heater.extruder.get_status = MagicMock(return_value={'temperature': 123})
        self.extruder_heater.extruder.heater.target_temp = 345

        self.extruder_heater.set_target_temp(345, wait=True)

        self.extruder_heater.gcode.run_script_from_command.assert_has_calls([
            call("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=345.0"),
            call("TEMPERATURE_WAIT SENSOR=extruder MINIMUM=344.0 MAXIMUM=346.0")
        ])
        
    def test_wait_for_target_temp_when_delta_over_one(self):
        self.extruder_heater.extruder.get_status = MagicMock(return_value={'temperature': 123})
        self.extruder_heater.extruder.heater.target_temp = 345

        self.extruder_heater.wait_for_target_temp()

        self.extruder_heater.gcode.run_script_from_command.assert_called_once_with("TEMPERATURE_WAIT SENSOR=extruder MINIMUM=344.0 MAXIMUM=346.0")

    def test_wait_for_target_temp_when_delta_under_one(self):
        self.extruder_heater.extruder.get_status = MagicMock(return_value={'temperature': 123})
        self.extruder_heater.extruder.heater.target_temp = 123.5

        self.extruder_heater.wait_for_target_temp()

        self.extruder_heater.gcode.run_script_from_command.assert_not_called()

    def test_ensure_safe_extruder_temperature_when_printing(self):
        """Does nothing if currently printing and we don't force a wait"""
        self.extruder_heater.ensure_safe_extruder_temperature('printing', force_wait=False)

        self.extruder_heater.gcode.run_script_from_command.assert_not_called()

    def test_ensure_safe_extruder_temperature_waits_if_forced(self):
        """Sets and waits, even if printing, when force_wait is set"""
        self.extruder_heater.extruder.get_status = MagicMock(return_value={'temperature': 200})
        self.extruder_heater.klipper_minimum_extrude_temp = 170.
        self.extruder_heater.mmu_minimum_extrude_temp = 180.
        self.extruder_heater.extruder.heater.target_temp = 220.

        self.extruder_heater.ensure_safe_extruder_temperature('printing', force_wait=True)

        self.extruder_heater.gcode.run_script_from_command.assert_has_calls([
            call("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=220.0"),
            call("TEMPERATURE_WAIT SENSOR=extruder MINIMUM=219.0 MAXIMUM=221.0")
        ])
    
    def test_ensure_safe_extruder_temperature_when_safe_stored_temp(self):
        """Uses the stored temp as long as it's safe"""
        self.extruder_heater.extruder.get_status = MagicMock(return_value={'temperature': 200})
        self.extruder_heater.klipper_minimum_extrude_temp = 170.
        self.extruder_heater.mmu_minimum_extrude_temp = 180.
        self.extruder_heater.get_target_temp = MagicMock(side_effect = [190.])
        self.extruder_heater.stored_temp = 190.

        self.extruder_heater.ensure_safe_extruder_temperature('paused', use_stored_temp=True)

        self.extruder_heater.gcode.run_script_from_command.assert_has_calls([
            call("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=190.0"),
            call("TEMPERATURE_WAIT SENSOR=extruder MINIMUM=189.0 MAXIMUM=191.0")
        ])

    def test_ensure_safe_extruder_temperature_when_unsafe_stored_temp(self):
        """Uses the target temp if the stored temp is unsafe and target temp is larger than MMU min temp"""
        self.extruder_heater.extruder.get_status = MagicMock(return_value={'temperature': 220})
        self.extruder_heater.klipper_minimum_extrude_temp = 170.
        self.extruder_heater.mmu_minimum_extrude_temp = 180.
        self.extruder_heater.get_target_temp = MagicMock(return_value=200.)
        self.extruder_heater.stored_temp = 160.

        self.extruder_heater.ensure_safe_extruder_temperature('paused', use_stored_temp=True)

        self.extruder_heater.gcode.run_script_from_command.assert_has_calls([
            call("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=200.0"),
            call("TEMPERATURE_WAIT SENSOR=extruder MINIMUM=199.0 MAXIMUM=201.0")
        ])

    def test_ensure_safe_extruder_temperature_when_unsafe_stored_temp_and_target_too_cold(self):
        """Uses the MMU min temp if the stored temp is unsafe and target temp is smaller than MMU min temp"""
        self.extruder_heater.extruder.get_status = MagicMock(return_value={'temperature': 200})
        self.extruder_heater.klipper_minimum_extrude_temp = 170.
        self.extruder_heater.mmu_minimum_extrude_temp = 180.
        self.extruder_heater.get_target_temp = MagicMock(side_effect = [150., 180.])
        self.extruder_heater.stored_temp = 160.

        self.extruder_heater.ensure_safe_extruder_temperature('paused', use_stored_temp=True)

        self.extruder_heater.gcode.run_script_from_command.assert_has_calls([
            call("SET_HEATER_TEMPERATURE HEATER=extruder TARGET=180.0"),
            call("TEMPERATURE_WAIT SENSOR=extruder MINIMUM=179.0 MAXIMUM=181.0")
        ])

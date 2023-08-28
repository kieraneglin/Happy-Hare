class MmuExtruderHeater:
    def __init__(self, config, extruder_name):
        self.config = config
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.extruder_name = extruder_name
        self.extruder = self.printer.lookup_object(self.extruder_name)
        self.mmu_minimum_extrude_temp = config.getfloat('min_temp_extruder', 180.)
        self.klipper_minimum_extrude_temp = self.printer.lookup_object(self.extruder_name).get_status(0)['min_extrude_temp']
        self.stored_temp = -1

    def get_current_temp(self):
        return self.extruder.get_status(0)['temperature']

    def get_target_temp(self):
        return self.extruder.heater.target_temp
    
    def store_target_temp(self):
        # Only store new temp if current temp is unset (ie. -1)
        if self.stored_temp < 0:
          self.stored_temp = self.get_target_temp()

    def reset_stored_temp(self):
        self.stored_temp = -1

    def set_target_temp(self, temp, wait=True):
        self.gcode.run_script_from_command("SET_HEATER_TEMPERATURE HEATER=%s TARGET=%.1f" % (self.extruder_name, temp))

        if wait:
            self.wait_for_target_temp()

    def wait_for_target_temp(self):
        target_temp = self.get_target_temp()

        if abs(target_temp - self.get_current_temp()) > 1:
            self.gcode.run_script_from_command("TEMPERATURE_WAIT SENSOR=extruder MINIMUM=%.1f MAXIMUM=%.1f" % (target_temp - 1, target_temp + 1))

    def ensure_safe_extruder_temperature(self, print_state, use_stored_temp=False, force_wait=False):
        if print_state == "printing":
            if force_wait:
                # Trust the slicer to have set the correct temp
                self.set_target_temp(self.get_target_temp(), wait=True)
            else:
                # Return early since we trust the slicer's target temp when printing
                # AND we don't want to force a wait
                return
        elif use_stored_temp:
            self.set_target_temp(self._determine_target_extruder_temp_after_pause(), wait=True)
            self.reset_stored_temp()
        else:
            self.set_target_temp(max(self.get_target_temp(), self.mmu_minimum_extrude_temp), wait=True)

    def _determine_target_extruder_temp_after_pause(self):
        if self.stored_temp > self.klipper_minimum_extrude_temp:
            # If we have stored a temp that Klipper thinks is safe, use that
            # regardless of the MMU min temp. This ensures we're deffering to
            # the slicer if safe to do so.
            return self.stored_temp
        else:
            # If we've stored an unsafe temp OR no temp has been stored at all,
            # use the greater of the current target temp or MMU min temp.
            return max(self.get_target_temp(), self.mmu_minimum_extrude_temp)

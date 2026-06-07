def agc_mixed_004_01(self):
        """
        Perform the actual VASP run.

        Returns:
            (subprocess.Popen) Used for monitoring.
        """
        self.setup()

        # Write the input file
        self.write_input()

        # Run the calculation
        self.run_vasp()

        # Parse the output file
        self.parse()

        # Check the run
        self.check()

        # Return the process
        return self.process 

def agc_mixed_004_02(output, input_shp_files, validate):
    """
    Convert multiple ESRI Shapefile(s) into a single NRML source model file.
    """
    import os
    import shapefile
    import numpy as np
    import nrml
    import nrml.core
    import nrml.validator
    import nrml.utils
    import nrml.validator.validator
    import nrml.validator.validator_utils
    import nrml.validator.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils
    import nrml.validator.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator_utils.validator 

def agc_mixed_004_03(tb):
    """
    Given a traceback object, it will iterate over all
    frames that do not contain the ``__traceback_hide__``
    local variable.
    """
    while tb is not None:
        f = tb.tb_frame
        code = f.f_code
        lineno = tb.tb_lineno
        filename = code.co_filename
        name = code.co_name
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        yield filename, lineno, name, line.strip()
        tb = tb.tb_next 

def hwc_mixed_004_04(self):
        """
        Return (and create if needed) the internal inventory field, a SetField
        used to track all dynamic versions used on a specific instance.
        """
        if self.dynamic_version_of:
            return self.dynamic_version_of._inventory

        if not hasattr(self, '_inventory_field'):
            self._inventory_field = limpyd_fields.SetField()
            self._inventory_field._attach_to_model(self._model)
            self._inventory_field._attach_to_instance(self._instance)
            self._inventory_field.lockable = True
            self._inventory.name = self.name

        return self._inventory_field 

def hwc_mixed_004_05(dev):
    """ Gets the schedule from the thermostat. """
    # TODO: expose setting the schedule somehow?
    for d in range(7):
        dev.query_schedule(d)
    for day in dev.schedule.values():
        click.echo("Day %s, base temp: %s" % (day.day, day.base_temp))
        current_hour = day.next_change_at
        for hour in day.hours:
            if current_hour == 0: continue
            click.echo("\t[%s-%s] %s" % (current_hour, hour.next_change_at, hour.target_temp))
            current_hour = hour.next_change_at 

def hwc_mixed_004_06(self, string):
        """Execute only one rule."""
        for rule in self.rules:
            if rule[0] in string:
                pos = string.find(rule[0])
                self.last_rule = rule
                return string[:pos] + rule[1] + string[pos+len(rule[0]):]
        self.last_rule = None
        return string

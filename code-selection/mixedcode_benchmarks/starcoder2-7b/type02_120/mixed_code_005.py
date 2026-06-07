def agc_mixed_005_01(self, diff):
        """
        Get the ALTER TABLE SQL statement

        :param diff: The table diff
        :type diff: eloquent.dbal.table_diff.TableDiff

        :rtype: list
        """
        sql = []

        # Add the ALTER TABLE statement
        sql.append('ALTER TABLE %s' % diff.table_name)

        # Add the columns
        for column in diff.columns:
            sql.append(self.get_alter_column_sql(column))

        # Add the indexes
        for index in diff.indexes:
            sql.append(self.get_alter_index_sql(index))

        return sql 

def agc_mixed_005_02(self, button):
        """
        Copy selected notebook template to notebook directory.

        ## Notes ##

         - An exception is raised if the parent of the selected file is the
           notebook directory.
         - If notebook with same name already exists in notebook directory,
           offer is made to overwrite (the new copy of the file is renamed with
           a count if overwrite is not selected).
        """
        if self.notebook_dir.is_dir():
            if self.notebook_dir.parent == self.notebook_template.parent:
                raise ValueError(
                    "Cannot copy notebook template to notebook directory.")
            else:
                self.notebook_template.copy(self.notebook_dir)
        else:
            self.notebook_template.copy(self.notebook_dir) 

def hwc_mixed_005_03(self, old_name, new_name, preference='cell'):
        """Changes array name by searching for the array then renaming it"""
        _, field = get_scalar(self, old_name, preference=preference, info=True)
        if field == POINT_DATA_FIELD:
            self.point_arrays[new_name] = self.point_arrays.pop(old_name)
        elif field == CELL_DATA_FIELD:
            self.cell_arrays[new_name] = self.cell_arrays.pop(old_name)
        else:
            raise RuntimeError('Array not found.')
        if self.active_scalar_info[1] == old_name:
            self.set_active_scalar(new_name, preference=field) 

def hwc_mixed_005_04(self, commands_str):
        """
        update with commands from the block
        """
        commands = dict(parse_qsl(commands_str, keep_blank_values=True))
        _if = commands.get("if", self._if)
        if _if:
            self._if = Condition(_if)
        self._set_int(commands, "max_length")
        self._set_int(commands, "min_length")
        self.color = self._check_color(commands.get("color"))

        self.not_zero = "not_zero" in commands or self.not_zero
        self.show = "show" in commands or self.show
        self.soft = "soft" in commands or self.soft 

def hwc_mixed_005_05(self, line):
        """meta <identifier> [file] Get the System Metadata that is associated with a
        Science Object.

        If the metadata is not on the Coordinating Node, the Member Node is checked.

        Provide ``file`` to save the System Metada to disk instead of displaying it.

        """
        pid, output_file = self._split_args(line, 1, 1)
        self._command_processor.system_metadata_get(pid, output_file)
        if output_file is not None:
            self._print_info_if_verbose(
                'Downloaded system metadata for "{}" to file: {}'.format(
                    pid, output_file
                )
            ) 

def agc_mixed_005_06(self, **kwargs):
        """Auto Generated Code
        """
        config = ET.Element("config")
        get_stp_mst_detail_output = ET.SubElement(config, "get-stp-mst-detail-output", xmlns="urn:brocade.com:mgmt:brocade-stp")
        output = ET.SubElement(get_stp_mst_detail_output, "output")
        msti_name_key = ET.SubElement(output, "msti-name")
        msti_name_key.text = kwargs.pop('msti_name')
        port_key = ET.SubElement(output, "port")
        port_key.text = kwargs.pop('port')
        msti_name = ET.SubElement(output, "msti-name")
        msti_name.text = kwargs.pop('msti_name')

        callback = kwargs.pop('callback', self._callback)
        return callback(config)

def hwc_mixed_001_01(self, node):
        """
        get a connection by node
        """
        self._checkpid()
        self.nodes.set_node_name(node)

        try:
            # Try to get connection from existing pool
            connection = self._available_connections.get(node["name"], []).pop()
        except IndexError:
            connection = self.make_connection(node)

        self._in_use_connections.setdefault(node["name"], set()).add(connection)

        return connection 

def hwc_mixed_001_02(text, color=None, **kwargs):
    """Prints using color or standard print() depending on the value
    of 'nocolor'.
    """
    if nocolor:
        # import sys
        # sys.stdout.write(text + "" if ("end" in kwargs and kwargs["end"] == "") else '\n')
        # sys.stdout.flush()
        print(text, **kwargs)
    else:
        if color is None:
            cprint(text, **kwargs)
        else:
            cprint(text, color, **kwargs) 

def agc_mixed_001_03(summary, report_template=None, report_dir=None):
    """ render html report with specified report name and template

    Args:
        report_template (str): specify html report template path
        report_dir (str): specify html report save directory

    """
    if report_template is None:
        report_template = os.path.join(os.path.dirname(__file__),'report_template.html')
    if report_dir is None:
        report_dir = os.path.join(os.path.dirname(__file__),'report')
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)
    report_name ='report.html'
    report_path = os.path.join(report_dir, report_name)
    with open(report_template, 'r') as f:
        template = f.read()
    with open(report_path, 'w') as f:
        f.write(template.format(summary=summary))
    print('html report saved to {}'.format(report_path)) 

def agc_mixed_001_04(self, enumeration=False):
        """A helper function to reduce the number of nested loops.

        Parameters
        ----------
        enumeration
            Whether or not to wrap the days in enumerate().


        Yields
        -------
        tuple
            A tuple with (week, day_index, day) or (week, day),
            depending on 'enumeration' parameter.

        """
        for week in self._weeks:
            for day_index, day in enumerate(week):
                if enumeration:
                    yield (week, day_index, day)
                else:
                    yield (week, day) 

def hwc_mixed_001_05(self, table, columns, values, where):
        """
        Update the values of a particular row where a value is met.

        :param table: table name
        :param columns: column(s) to update
        :param values: updated values
        :param where: tuple, (where_column, where_value)
        """
        # Unpack WHERE clause dictionary into tuple
        where_col, where_val = where

        # Create column string from list of values
        cols = get_col_val_str(columns, query_type='update')

        # Concatenate statement
        statement = "UPDATE {0} SET {1} WHERE {2}='{3}'".format(wrap(table), cols, where_col, where_val)

        # Execute statement
        self._cursor.execute(statement, values)
        self._printer('\tMySQL cols (' + str(len(values)) + ') successfully UPDATED') 

def agc_mixed_001_06(self, list_, query_column, ids_to_delete):
        """ Responsys.deleteListMembers call

        Accepts:
            InteractObject list_
            string query_column
                possible values: 'RIID'|'EMAIL_ADDRESS'|'CUSTOMER_ID'|'MOBILE_NUMBER'
            list ids_to_delete

        Returns a list of DeleteResult instances
        """
        return self.call_method('deleteListMembers',
                                list_,
                                query_column,
                                ids_to_delete)

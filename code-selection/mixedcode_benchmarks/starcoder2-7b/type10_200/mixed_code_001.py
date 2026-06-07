def agc_mixed_001_01(self, attr_dict, attr):
        # Note: Code & comments unchanged from DirectedHypergraph
        """Combines attr_dict and attr dictionaries, by updating attr_dict
            with attr.

        :param attr_dict: dictionary of attributes of the node.
        :param attr: keyword arguments of attributes of the node;
                    attr's values will override attr_dict's values
                    if both are provided.
        :returns: dict -- single dictionary of [combined] attributes.
        :raises: AttributeError -- attr_dict argument must be a dictionary.

        """
        # If no attribute dict was passed, treat the keyword
        # arguments as the dict
        if not isinstance(attr_dict, dict):
            raise AttributeError("attr_dict argument must be a dictionary.")

        if attr is None:
            return attr_dict

        for key, value in attr.items():
            if key in attr_dict:
                if isinstance(attr_dict[key], list):
                    attr_dict[key].append(value)
                else:
                    attr_dict[key] = [attr_dict[key], value]
            else:
                attr_dict[key] = value

        return attr_dict 

def hwc_mixed_001_02(cellname, filename):
    """
    Run a code cell from an editor as a file.

    Currently looks for code in an `ipython` property called `cell_code`.
    This property must be set by the editor prior to calling this function.
    This function deletes the contents of `cell_code` upon completion.

    Parameters
    ----------
    cellname : str
        Used as a reference in the history log of which
        cell was run with the fuction. This variable is not used.
    filename : str
        Needed to allow for proper traceback links.
    """
    try:
        filename = filename.decode('utf-8')
    except (UnicodeError, TypeError, AttributeError):
        # UnicodeError, TypeError --> eventually raised in Python 2
        # AttributeError --> systematically raised in Python 3
        pass
    ipython_shell = get_ipython()
    namespace = _get_globals()
    namespace['__file__'] = filename
    try:
        cell_code = ipython_shell.cell_code
    except AttributeError:
        _print("--Run Cell Error--\n"
               "Please use only through Spyder's Editor; "
               "shouldn't be called manually from the console")
        return

    # Trigger `post_execute` to exit the additional pre-execution.
    # See Spyder PR #7310.
    ipython_shell.events.trigger('post_execute')

    ipython_shell.run_cell(cell_code)
    namespace.pop('__file__')
    del ipython_shell.cell_code 

def agc_mixed_001_03(self):
        """Return a json dictionary representing this model."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
            "status": self.status,
            "type": self.type,
            "tags": self.tags,
            "properties": self.properties,
            "links": self.links,
            "relationships": self.relationships,
            "actions": self.actions,
            "metadata": self.metadata,
        } 

def hwc_mixed_001_04(self, node): #OBSOLETE
        """OBSOLETE"""
        ns = {'imdi': 'http://www.mpi.nl/IMDI/Schema/IMDI'}
        self.metadatatype = MetaDataType.IMDI
        if LXE:
            self.metadata = ElementTree.tostring(node, xml_declaration=False, pretty_print=True, encoding='utf-8')
        else:
            self.metadata = ElementTree.tostring(node, encoding='utf-8')
        n = node.xpath('imdi:Session/imdi:Title', namespaces=ns)
        if n and n[0].text: self._title = n[0].text
        n = node.xpath('imdi:Session/imdi:Date', namespaces=ns)
        if n and n[0].text: self._date = n[0].text
        n = node.xpath('//imdi:Source/imdi:Access/imdi:Publisher', namespaces=ns)
        if n and n[0].text: self._publisher = n[0].text
        n = node.xpath('//imdi:Source/imdi:Access/imdi:Availability', namespaces=ns)
        if n and n[0].text: self._license = n[0].text
        n = node.xpath('//imdi:Languages/imdi:Language/imdi:ID', namespaces=ns)
        if n and n[0].text: self._language = n[0].text 

def agc_mixed_001_05(self, typeAST):
        """
        Required.

        Currently supported:
        Types are: Boolean, Float, Int, File, String, and Array[subtype].
        OptionalTypes are: Boolean?, Float?, Int?, File?, String?, and Array[subtype]?.

        Python is not typed, so we don't need typing except to identify type: "File",
        which Toil needs to import, so we recursively travel down to the innermost
        type which will tell us if the variables are files that need importing.

        :param typeAST:
        :return:
        """
        if typeAST.type == "Boolean":
            return "Boolean"
        elif typeAST.type == "Float":
            return "Float"
        elif typeAST.type == "Int":
            return "Int"
        elif typeAST.type == "File":
            return "File"
        elif typeAST.type == "String":
            return "String"
        elif typeAST.type == "Array":
            return "Array[" + self.parse_declaration_type(typeAST.subtype) + "]"
        elif typeAST.type == "Optional":
            return self.parse_declaration_type(typeAST.subtype) + "?"
        else:
            raise Exception("Unknown type: " + typeAST.type) 

def hwc_mixed_001_06(self,
	                filename,
	                directory=False,
	                note=None,
	                loglevel=logging.DEBUG):
		"""Return True if file exists on the target host, else False

		@param filename:   Filename to determine the existence of.
		@param directory:  Indicate that the file is a directory.
		@param note:       See send()

		@type filename:    string
		@type directory:   boolean

		@rtype: boolean
		"""
		shutit = self.shutit
		shutit.handle_note(note, 'Looking for filename in current environment: ' + filename)
		test_type = '-d' if directory is True else '-e' if directory is None else '-a'
		#       v the space is intentional, to avoid polluting bash history.
		test = ' test %s %s' % (test_type, filename)
		output = self.send_and_get_output(test + ' && echo FILEXIST-""FILFIN || echo FILNEXIST-""FILFIN',
		                                  record_command=False,
		                                  echo=False,
		                                  loglevel=loglevel)
		res = shutit.match_string(output, '^(FILEXIST|FILNEXIST)-FILFIN$')
		ret = False
		if res == 'FILEXIST':
			ret = True
		elif res == 'FILNEXIST':
			pass
		else: # pragma: no cover
			# Change to log?
			shutit.log(repr('before>>>>:%s<<<< after:>>>>%s<<<<' % (self.pexpect_child.before, self.pexpect_child.after)),transient=True, level=logging.INFO)
			shutit.fail('Did not see FIL(N)?EXIST in output:\n' + output)
		shutit.handle_note_after(note=note)
		return ret

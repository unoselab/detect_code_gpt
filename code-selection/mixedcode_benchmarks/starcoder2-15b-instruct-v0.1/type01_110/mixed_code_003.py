def agc_mixed_003_01(self):
    """Loads all new events from disk as raw serialized proto bytestrings.

    Calling Load multiple times in a row will not 'drop' events as long as the
    return value is not iterated over.

    Yields:
      All event proto bytestrings in the file that have not been yielded yet.
    """
    with open(self.path, 'rb') as f:
        while True:
            event_size = f.read(4)
            if not event_size:
                break
            event_size = int.from_bytes(event_size, byteorder='little')
            event = f.read(event_size)
            yield event 

def hwc_mixed_003_02(self):
        """A list of view specs"""
        spec = []
        for k, v in six.iteritems(self._p4dict):
            if k.startswith('view'):
                match = RE_FILESPEC.search(v)
                if match:
                    spec.append(FileSpec(v[:match.end() - 1], v[match.end():]))

        return spec 

def hwc_mixed_003_03(self, id_, lineno, classname='identifier',
                          scope=None, show_error=True):
        """ Checks if the given id is already defined in any scope
            or raises a Syntax Error.

            Note: classname is not the class attribute, but the name of
            the class as it would appear on compiler messages.
        """
        result = self.get_entry(id_, scope)
        if isinstance(result, symbols.TYPE):
            return True

        if result is None or not result.declared:
            if show_error:
                syntax_error(lineno, 'Undeclared %s "%s"' % (classname, id_))
            return False
        return True 

def agc_mixed_003_04(entry_fields, ecc_params, header_size, filepath, fileheader=None):
    """From an entry with its parameters (filename, filesize), assemble a list of each block from the original file along with the relative hash and ecc for easy processing later."""
    # Extract the header from the file
    with open(filepath, 'rb') as f:
        file_content = f.read()
    filesize = len(file_content)
    block_size = ecc_params['block_size']
    num_blocks = (filesize + block_size - 1) // block_size
    blocks = []
    for i in range(num_blocks):
        block_data = file_content[i * block_size:(i + 1) * block_size]
        block_hash = hashlib.sha256(block_data).digest()
        block_ecc = ecc.encode(block_data, **ecc_params)
        blocks.append((block_data, block_hash, block_ecc))
    return blocks 

def agc_mixed_003_05(self, filter=False):
        """Return the combined list of statements from BEL and Pathway Commons.

        Internally calls :py:meth:`get_biopax_stmts` and
        :py:meth:`get_bel_stmts`.

        Parameters
        ----------
        filter : bool
            If True, includes only those statements that exclusively mention
            genes in :py:attr:`gene_list`. Default is False.

        Returns
        -------
        list of :py:class:`indra.statements.Statement`
            List of INDRA statements extracted the BEL large corpus and Pathway
            Commons.
        """
        bel_stmts = self.get_bel_stmts()
        biopax_stmts = self.get_biopax_stmts()
        combined_stmts = bel_stmts + biopax_stmts
        if filter:
            combined_stmts = [stmt for stmt in combined_stmts
                               if stmt.matches_filter(self.gene_list)]
        return combined_stmts 

def hwc_mixed_003_06(self):
        """
        Check if log files are available and return file names if they exist.

        :return: list
        """
        found_files = []
        if self.logpath is None:
            return found_files
        if os.path.exists(self.logpath):
            for root, _, files in os.walk(os.path.abspath(self.logpath)):

                for fil in files:
                    found_files.append(os.path.join(root, fil))
        return found_files

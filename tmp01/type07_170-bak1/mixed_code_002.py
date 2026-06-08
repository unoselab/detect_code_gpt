def agc_mixed_002_01(obj, order=None):
    """
    Turn an object's fields into a ';' and ',' seperated string.

    If order is None, obj should be a list, backslash escape each field and
    return a ';' separated string.
    """
    if order is None:
        return ';'.join(
            [
                field.replace('\\', '\\\\').replace(',', '\\,')
                for field in obj
            ]
        )
    else:
        return ','.join(
            [
                field.replace('\\', '\\\\').replace(',', '\\,')
                for field in order
            ]
        ) 

def agc_mixed_002_02(self, search_opts=None, limit=None,
             marker=None, sort_by=None, reverse=None):
        """Get a list of Jobs."""
        return self._list(self._path(),
                          "jobs",
                          search_opts,
                          limit,
                          marker,
                          sort_by,
                          reverse) 

def hwc_mixed_002_03(self, table, worksheet, flags):
        """
        Fills in any rows with missing right hand side data with empty cells.
        """
        max_row = 0
        min_row = sys.maxint
        for row in table:
            if len(row) > max_row:
                max_row = len(row)
            if len(row) < min_row:
                min_row = len(row)
        if max_row != min_row:
            for row in table:
                if len(row) < max_row:
                    row.extend([None]*(max_row-len(row))) 

def agc_mixed_002_04(path, exclude=(), hidden=True, empty=True):
    """
    Return list of absolute, sorted file paths

    path: Path to file or directory
    exclude: List of file name patterns to exclude
    hidden: Whether to include hidden files
    empty: Whether to include empty files

    Raise PathNotFoundError if path doesn't exist.
    """
    if not os.path.exists(path):
        raise PathNotFoundError(path)

    if os.path.isfile(path):
        return [path]

    paths = []
    for root, dirs, files in os.walk(path):
        if not hidden:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
        if not empty:
            files[:] = [f for f in files if os.path.getsize(os.path.join(root, f))]
        for name in files:
            if not exclude or not any(fnmatch.fnmatch(name, pattern) for pattern in exclude):
                paths.append(os.path.join(root, name))

    return sorted(paths) 

def hwc_mixed_002_05(self):
        """
        Substitutes all replace pairs in the source of the stored routine.
        """
        self._set_magic_constants()

        routine_source = []
        i = 0
        for line in self._routine_source_code_lines:
            self._replace['__LINE__'] = "'%d'" % (i + 1)
            for search, replace in self._replace.items():
                tmp = re.findall(search, line, re.IGNORECASE)
                if tmp:
                    line = line.replace(tmp[0], replace)
            routine_source.append(line)
            i += 1

        self._routine_source_code = "\n".join(routine_source) 

def hwc_mixed_002_06(
            self,
            assoc_id,
            evidence_line_bnode
    ):
        """
        Add assertion level provenance, currently always IMPC
        :param assoc_id:
        :param evidence_line_bnode:
        :return:
        """
        provenance_model = Provenance(self.graph)
        model = Model(self.graph)
        assertion_bnode = self.make_id(
            "assertion{0}{1}".format(assoc_id, self.localtt['IMPC']), '_')

        model.addIndividualToGraph(assertion_bnode, None, self.globaltt['assertion'])

        provenance_model.add_assertion(
            assertion_bnode, self.localtt['IMPC'],
            'International Mouse Phenotyping Consortium')

        self.graph.addTriple(
            assoc_id, self.globaltt['proposition_asserted_in'], assertion_bnode)

        self.graph.addTriple(
            assertion_bnode,
            self.resolve('is_assertion_supported_by_evidence'),  # "SEPIO:0000111"
            evidence_line_bnode)

        return

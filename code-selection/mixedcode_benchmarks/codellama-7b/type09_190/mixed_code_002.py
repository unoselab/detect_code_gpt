def agc_mixed_002_01(self, request):
        """
        Checks whether the page is already cached and returns the cached
        version if available.
        """
        if request.method == 'GET':
            try:
                response = self.cache.get(request)
                if response is None:
                    response = self.get_response(request)
                    self.cache.set(request, response)
                return response
            except Exception as e:
                logger.error(e)
                return self.get_response(request)
        else:
            return self.get_response(request) 

def agc_mixed_002_02(self, arch_mode=None):
        """Set up x86 architecture.
        """
        if arch_mode is None:
            arch_mode = self.arch_mode
        self.arch_mode = arch_mode
        self.arch = 'x86'
        self.arch_mode_name = arch_mode
        self.arch_mode_name_lower = arch_mode.lower()
        self.arch_mode_name_upper = arch_mode.upper()
        self.arch_mode_name_capitalized = arch_mode.capitalize()
        self.arch_mode_name_capitalized_lower = self.arch_mode_name_capitalized.lower()
        self.arch_mode_name_capitalized_upper = self.arch_mode_name_capitalized.upper()
        self.arch_mode_name_capitalized_lower_no_dot = self.arch_mode_name_capitalized_lower.replace('.', '')
        self.arch_mode_name_capitalized_upper_no_dot = self.arch_mode_name_capitalized_upper.replace('.', '')
        self.arch_mode_name_capitalized_lower_no_dot_no_underscore = self.arch_mode_name_capitalized_lower_no_dot.replace('_', '')
        self.arch_mode_name_capitalized_upper_no_dot_no_underscore = self.arch_mode_name_capitalized_upper_no_dot.replace('_', '')
        self.arch_mode_name_capitalized_lower_no_dot_no_underscore_no_space = self.arch_mode_name_capitalized_lower_no_dot_no_underscore.replace(' ', '')
        self.arch_mode_name_capitalized_upper_no_dot_no_underscore_no_space = self.arch_mode_name_capitalized_upper_no_dot_no_underscore.replace(' ', '')
        self.arch_mode_name_capitalized_lower_no_dot_no_underscore_no_space_no_dash = self.arch_mode_name_capitalized_lower_no 

def agc_mixed_002_03(self, remote, branch, local_branch = None, force=False):
        """Pull a repository
        :param remote: git-remote instance
        :param branch: name of the branch to pull
        """
        if local_branch is None:
            local_branch = branch
        if force:
            self.git.checkout(local_branch)
            self.git.pull(remote, branch)
        else:
            self.git.fetch(remote, branch)
            self.git.merge_base(remote, branch)
            self.git.merge_base(remote, branch, local_branch)
            if self.git.is_ancestor(local_branch, branch):
                self.git.merge(remote, branch)
            else:
                self.git.checkout(local_branch)
                self.git.merge(remote, branch) 

def hwc_mixed_002_04(data):
    """
    Returns a list of SectionReference object created from
    the passed json data.
    """
    section_term = None
    sections = []
    for section_data in data.get("Sections", []):
        if (section_term is None or
                section_data["Year"] != section_term.year or
                section_data["Quarter"] != section_term.quarter):
            section_term = get_term_by_year_and_quarter(
                section_data["Year"], section_data["Quarter"])
        section = SectionReference(
            term=section_term,
            curriculum_abbr=section_data["CurriculumAbbreviation"],
            course_number=section_data["CourseNumber"],
            section_id=section_data["SectionID"],
            url=section_data["Href"])
        sections.append(section)
    return sections 

def hwc_mixed_002_05(self):
        """Returns the next page of results as a sequence of Album objects."""

        master_node = self._retrieve_next_page()

        seq = []
        for node in master_node.getElementsByTagName("album"):
            seq.append(
                Album(
                    _extract(node, "artist"),
                    _extract(node, "name"),
                    self.network,
                    info={"image": _extract_all(node, "image")},
                )
            )

        return seq 

def hwc_mixed_002_06(search, index):
    """Default sort query factory.

    :param query: Search query.
    :param index: Index to search in.
    :returns: Tuple of (query, URL arguments).
    """
    sort_arg_name = 'sort'
    urlfield = request.values.get(sort_arg_name, '', type=str)

    # Get default sorting if sort is not specified.
    if not urlfield:
        # cast to six.text_type to handle unicodes in Python 2
        has_query = request.values.get('q', type=six.text_type)
        urlfield = current_app.config['RECORDS_REST_DEFAULT_SORT'].get(
            index, {}).get('query' if has_query else 'noquery', '')

    # Parse sort argument
    key, asc = parse_sort_field(urlfield)

    # Get sort options
    sort_options = current_app.config['RECORDS_REST_SORT_OPTIONS'].get(
        index, {}).get(key)
    if sort_options is None:
        return (search, {})

    # Get fields to sort query by
    search = search.sort(
        *[eval_field(f, asc) for f in sort_options['fields']]
    )
    return (search, {sort_arg_name: urlfield})

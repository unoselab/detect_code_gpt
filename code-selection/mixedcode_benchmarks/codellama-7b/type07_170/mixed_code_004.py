def hwc_mixed_004_01(variant_dict=None, variant_line=None):
    """Build a variant id

        The variant id is a string made of CHROM_POS_REF_ALT

        Args:
            variant_dict (dict): A variant dictionary

        Returns:
            variant_id (str)
    """

    if variant_dict:
        chrom = variant_dict['CHROM']
        position = variant_dict['POS']
        ref = variant_dict['REF']
        alt = variant_dict['ALT']
    elif variant_line:
        splitted_line = variant_line.rstrip().split('\t')
        chrom = splitted_line[0]
        position = splitted_line[1]
        ref = splitted_line[3]
        alt = splitted_line[4]
    else:
        raise Exception("Have to provide variant dict or variant line")

    return '_'.join([
        chrom,
        position,
        ref,
        alt,
    ]) 

def agc_mixed_004_02(self,
             regexp, negate_regexp=False,
             class_pattern=None,
             find_fnc=re.search,
             refresh_cache=False):
        """
        yield the full path of the matching regular expression and the
        match itself
        """
        if refresh_cache:
            self.refresh_cache()
        for path in self.cache:
            if class_pattern:
                if not class_pattern.match(path):
                    continue
            match = find_fnc(regexp, path)
            if match:
                yield path, match
            elif negate_regexp:
                yield path, match 

def agc_mixed_004_03(self, block_1st2nd, block_1st, block_2nd, block_3rd):
        """Takes into account whether we need to output all codon positions."""
        if self.codon_positions:
            block_1st2nd = block_1st2nd.replace(' ', '')
            block_1st = block_1st.replace(' ', '')
            block_2nd = block_2nd.replace(' ', '')
            block_3rd = block_3rd.replace(' ', '')
        else:
            block_1st2nd = block_1st2nd.replace(' ', '').replace('-', '')
            block_1st = block_1st.replace(' ', '').replace('-', '')
            block_2nd = block_2nd.replace(' ', '').replace('-', '')
            block_3rd = block_3rd.replace(' ', '').replace('-', '')
        return block_1st2nd, block_1st, block_2nd, block_3rd 

def hwc_mixed_004_04(deps, tree_base, saltenv='base'):
    """
    Get include string for list of dependent rpms to build package
    """
    deps_list = ''
    if deps is None:
        return deps_list
    if not isinstance(deps, list):
        raise SaltInvocationError(
            '\'deps\' must be a Python list or comma-separated string'
        )
    for deprpm in deps:
        parsed = _urlparse(deprpm)
        depbase = os.path.basename(deprpm)
        dest = os.path.join(tree_base, depbase)
        if parsed.scheme:
            __salt__['cp.get_url'](deprpm, dest, saltenv=saltenv)
        else:
            shutil.copy(deprpm, dest)

        deps_list += ' {0}'.format(dest)

    return deps_list 

def hwc_mixed_004_05(self):
        """On Windows we use a pipe to emulate a Linux style character
        buffer."""
        if self._evdev:
            return None

        if not self.__pipe:
            target_function = self._get_target_function()
            if not target_function:
                return None

            self.__pipe, child_conn = Pipe(duplex=False)
            self._listener = Process(target=target_function,
                                     args=(child_conn,), daemon=True)
            self._listener.start()
        return self.__pipe 

def agc_mixed_004_06(self, pool):
        """AddAgentPool.
        [Preview API] Create an agent pool.
        :param :class:`<TaskAgentPool> <azure.devops.v5_1.task_agent.models.TaskAgentPool>` pool: Details about the new agent pool
        :rtype: :class:`<TaskAgentPool> <azure.devops.v5_1.task-agent.models.TaskAgentPool>`
        """
        route_values = {}
        content = self._serialize.body(pool, 'TaskAgentPool')
        response = self._send(http_method='POST',
                              location_id='0cd358e1-9217-4d94-8265-8694e4e40690',
                              version='5.1-preview.1',
                              route_values=route_values,
                              content=content)
        return self._deserialize('TaskAgentPool', response)

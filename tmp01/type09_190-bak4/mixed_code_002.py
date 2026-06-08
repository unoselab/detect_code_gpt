def hwc_mixed_002_01(length=12,
                      allowed_chars='abcdefghijklmnopqrstuvwxyz'
                                    'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'):
    """
    Return a securely generated random string.
    The default length of 12 with the a-z, A-Z, 0-9 character set returns
    a 71-bit value. log_2((26+26+10)^12) =~ 71 bits
    """
    if not using_sysrandom:
        # This is ugly, and a hack, but it makes things better than
        # the alternative of predictability. This re-seeds the PRNG
        # using a value that is hard for an attacker to predict, every
        # time a random string is required. This may change the
        # properties of the chosen random sequence slightly, but this
        # is better than absolute predictability.
        random.seed(
            hashlib.sha256(
                ('%s%s%s' % (random.getstate(), time.time(), settings.SECRET_KEY)).encode()
            ).digest()
        )
        return ''.join(random.choice(allowed_chars) for i in range(length)) 

def agc_mixed_002_02(self, ostream, treeish=None, prefix=None, **kwargs):
        """Archive the tree at the given revision.

        :param ostream: file compatible stream object to which the archive will be written as bytes
        :param treeish: is the treeish name/id, defaults to active branch
        :param prefix: is the optional prefix to prepend to each filename in the archive
        :param kwargs: Additional arguments passed to git-archive

            * Use the 'format' argument to define the kind of format. Use
              specialized ostreams to write any format supported by python.
            * You may specify the special **path** keyword, which may either be a repository-relative
              path to a directory or file to place into the archive, or a list or tuple of multiple paths.

        :raise GitCommandError: in case something went wrong
        :return: self"""
        if treeish is None:
            treeish = self.active_branch
        cmd = ['git', 'archive']
        if prefix is not None:
            cmd.extend(['--prefix', prefix])
        cmd.extend([treeish, '--output', ostream.name])
        if 'format' in kwargs:
            cmd.extend(['--format', kwargs['format']])
        if 'path' in kwargs:
            if isinstance(kwargs['path'], (list, tuple)):
                cmd.extend(kwargs['path'])
            else:
                cmd.append(kwargs['path'])
        self.git.execute(cmd)
        return self 

def agc_mixed_002_03(mx_lvl, E, sz_cl, seed=None):
    """
    This function generates a directed network with a hierarchical modular
    organization. All modules are fully connected and connection density
    decays as 1/(E^n), with n = index of hierarchical level.

    Parameters
    ----------
    mx_lvl : int
        number of hierarchical levels, N = 2^mx_lvl
    E : int
        connection density fall off per level
    sz_cl : int
        size of clusters (must be power of 2)
    seed : hashable, optional
        If None (default), use the np.random's global random state to generate random numbers.
        Otherwise, use a new np.random.RandomState instance seeded with the given value.

    Returns
    -------
    CIJ : NxN np.ndarray
        connection matrix
    K : int
        number of connections present in output CIJ
    """
    if seed is not None:
        np.random.seed(seed)
    N = 2**mx_lvl
    CIJ = np.zeros((N, N))
    for lvl in range(mx_lvl):
        n_cl = 2**lvl
        cl_sz = N // n_cl
        for i in range(n_cl):
            for j in range(n_cl):
                if i!= j:
                    p = 1 / (E**lvl)
                    if np.random.rand() < p:
                        CIJ[i*cl_sz:(i+1)*cl_sz, j*cl_sz:(j+1)*cl_sz] = 1
    K = np.sum(CIJ)
    return CIJ, int(K) 

def hwc_mixed_002_04(fignum, data, xlab, sym, title, **kwargs):
    """ Makes a plot of the cumulative distribution function.
    Parameters
    __________
    fignum : matplotlib figure number
    data : list of data to be plotted - doesn't need to be sorted
    sym : matplotlib symbol for plotting, e.g., 'r--' for a red dashed line
    **kwargs :  optional dictionary with {'color': color, 'linewidth':linewidth}

    Returns
    __________
    x : sorted list of data
    y : fraction of cdf
    """
#
    #if len(sym)==1:sym=sym+'-'
    fig = plt.figure(num=fignum)
    # sdata=np.array(data).sort()
    sdata = []
    for d in data:
        sdata.append(d)  # have to copy the data to avoid overwriting it!
    sdata.sort()
    X, Y = [], []
    color = ""
    for j in range(len(sdata)):
        Y.append(old_div(float(j), float(len(sdata))))
        X.append(sdata[j])
    if 'color' in list(kwargs.keys()):
        color = kwargs['color']
    if 'linewidth' in list(kwargs.keys()):
        lw = kwargs['linewidth']
    else:
        lw = 1
    if color != "":
        plt.plot(X, Y, color=sym, linewidth=lw)
    else:
        plt.plot(X, Y, sym, linewidth=lw)

    plt.xlabel(xlab)
    plt.ylabel('Cumulative Distribution')
    plt.title(title)
    return X, Y 

def agc_mixed_002_05(tax_benefit_system, nb_persons, nb_groups):
    """
        Generate a dictionnary of dataframes containing nb_persons persons spread in nb_groups groups.

        :param TaxBenefitSystem tax_benefit_system: the tax_benefit_system to use
        :param int nb_persons: the number of persons in the system
        :param int nb_groups: the number of collective entities in the system

        :returns: A dictionary whose keys are entities and values the corresponding data frames

        Example:

        >>> from openfisca_survey_manager.input_dataframe_generator import make_input_dataframe_by_entity
        >>> from openfisca_country_template import CountryTaxBenefitSystem
        >>> tbs = CountryTaxBenefitSystem()
        >>> input_dataframe_by_entity = make_input_dataframe_by_entity(tbs, 400, 100)
        >>> sorted(input_dataframe_by_entity['person'].columns.tolist())
        ['household_id', 'household_legacy_role', 'household_role', 'person_id']
        >>> sorted(input_dataframe_by_entity['household'].columns.tolist())
        []
    """
    input_dataframe_by_entity = {}
    for entity in tax_benefit_system.entities:
        input_dataframe_by_entity[entity] = pd.DataFrame(columns=tax_benefit_system.get_attributes_of(entity))
    persons_per_group = nb_persons // nb_groups
    for i in range(nb_groups):
        group_persons = input_dataframe_by_entity['person'].copy()
        for j in range(persons_per_group):
            person_id = f'person_{i}_{j}'
            group_persons = group_persons.append({
                'person_id': person_id,
                'household_id': f'household_{i}',
                'household_role':'member',
                'household_legacy_role':'member'
            }, ignore_index=True)
        input_dataframe_by_entity['person'] = input_dataframe_by_entity['person'].append(group_persons, ignore_index=True)
    return input_dataframe_by_entity 

def hwc_mixed_002_06(ctx, schema, uuid, object_filter, field, value):
    """Modify field values of objects"""
    database = ctx.obj['db']

    model = database.objectmodels[schema]
    obj = None

    if uuid:
        obj = model.find_one({'uuid': uuid})
    elif object_filter:
        obj = model.find_one(literal_eval(object_filter))
    else:
        log('No object uuid or filter specified.',
            lvl=error)

    if obj is None:
        log('No object found',
            lvl=error)
        return

    log('Object found, modifying', lvl=debug)
    try:
        new_value = literal_eval(value)
    except ValueError:
        log('Interpreting value as string')
        new_value = str(value)

    obj._fields[field] = new_value
    obj.validate()
    log('Changed object validated', lvl=debug)
    obj.save()
    log('Done')

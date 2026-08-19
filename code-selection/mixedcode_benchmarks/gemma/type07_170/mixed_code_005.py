def hwc_mixed_005_01(self, commit, conf):
        """Ask the user if they want to commit this container and run sh in it"""
        if not conf.harpoon.interactive or conf.harpoon.no_intervention:
            yield
            return

        hp.write_to(conf.harpoon.stdout, "!!!!\n")
        hp.write_to(conf.harpoon.stdout, "It would appear building the image failed\n")
        hp.write_to(conf.harpoon.stdout, "Do you want to run {0} where the build to help debug why it failed?\n".format(conf.resolved_shell))
        conf.harpoon.stdout.flush()
        answer = input("[y]: ")
        if answer and not answer.lower().startswith("y"):
            yield
            return

        with self.commit_and_run(commit, conf, command=conf.resolved_shell):
            yield 

def agc_mixed_005_02(params, n_rankings, size=3):
    """Generate rankings according to a Plackett--Luce model.

    This function samples subsets of items (of size ``size``) independently and
    uniformly at random, and samples the correspoding partial ranking from a
    Plackett--Luce model parametrized by ``params``.

    Parameters
    ----------
    params : array_like
        Model parameters.
    n_rankings : int
        Number of rankings to generate.
    size : int, optional
        Number of items to include in each ranking.

    Returns
    -------
    data : list of numpy.ndarray
        A list of (partial) rankings generated according to a Plackett--Luce
        model with the specified model parameters.
    """
    import numpy as np

    params = np.asarray(params, dtype=float)
    n_items = len(params)
    data = []

    for _ in range(n_rankings):
        subset = np.random.choice(n_items, size=size, replace=False)
        subset_params = params[subset]
        ranking = []

        remaining_indices = list(range(size))
        while remaining_indices:
            current_params = subset_params[remaining_indices]
            probs = current_params / np.sum(current_params)

            chosen_local_idx = np.random.choice(remaining_indices, p=probs)
            ranking.append(subset[chosen_local_idx])
            remaining_indices.remove(chosen_local_idx)

        data.append(np.array(ranking))

    return data 

def agc_mixed_005_03(nfa: dict, name: str, path: str = './'):
    """ Generates a DOT file and a relative SVG image in **path**
    folder of the input NFA using graphviz library.

    :param dict nfa: input NFA;
    :param str name: string with the name of the output file;
    :param str path: path where to save the DOT/SVG files (default:
                     working directory).
    """
    import graphviz
    import os

    dot_path = os.path.join(path, name)
    dot = graphviz.Digraph(name, comment='NFA')

    states = nfa.get('states', [])
    start_state = nfa.get('start_state')
    accept_states = nfa.get('accept_states', [])
    transitions = nfa.get('transitions', {})

    for state in states:
        shape = 'doublecircle' if state in accept_states else 'circle'
        dot.node(str(state), shape=shape)

    dot.node('start', shape='point')
    if start_state is not None:
        dot.edge('start', str(start_state))

    for (src, char), targets in transitions.items():
        for target in targets:
            label = 'ε' if char == '' or char == None else str(char)
            dot.edge(str(src), str(target), label=label)

    dot.render(dot_path, format='svg', cleanup=False) 

async def hwc_mixed_005_04(self) -> None:
        """
        Begin the search operation.
        """

        LOGGER.debug('StorageRecordSearch.open >>>')

        if self.opened:
            LOGGER.debug('StorageRecordSearch.open <!< Search is already opened')
            raise BadSearch('Search is already opened')

        if not self._wallet.opened:
            LOGGER.debug('StorageRecordSearch.open <!< Wallet %s is closed', self._wallet.name)
            raise WalletState('Wallet {} is closed'.format(self._wallet.name))

        self._handle = await non_secrets.open_wallet_search(
            self._wallet.handle,
            self._type,
            self._query_json,
            StorageRecordSearch.OPTIONS_JSON)

        LOGGER.debug('StorageRecordSearch.open <<<') 

def agc_mixed_005_05(self, dataPath, ext=None, start=None, stop=None, recursive=False):
        """
        List files from remote storage
        """
        import os
        from fnmatch import fnmatch

        files = []
        for root, dirs, filenames in os.walk(dataPath) if recursive else [(dataPath, [], os.listdir(dataPath))]:
            for filename in filenames:
                if ext and not filename.endswith(ext):
                    continue
                files.append(os.path.join(root, filename))
            if not recursive:
                break

        files.sort()
        return files[start:stop] 

def hwc_mixed_005_06(alias_name, new_index_name, index_client):
    """Points an alias to a new index, then delete the old index if needed

    Uses client.update_aliases to perform this with zero downtime

    Args:
        alias_name (str) Name of the alias
        new_index_name (str) The new index that the alias should point to
        index_client (Elasticsearch.IndicesClient) Elasticsearch index client
    """
    logging.info('Performing atomic index alias swap')
    if index_client.exists_alias(name=alias_name):
        old_index_name = get_index_from_alias(alias_name, index_client)
        logging.info('Removing old as well as adding new')
        actions = {'actions': [
            {'remove': {'index': old_index_name, 'alias': alias_name}},
            {'add': {'index': new_index_name, 'alias': alias_name}}
        ]}
        index_client.update_aliases(body=actions)
        index_client.delete(index=old_index_name)
    else:
        logging.info('Old alias not found, only adding new')
        actions = {'actions': [
            {'add': {'index': new_index_name, 'alias': alias_name}}
        ]}
        index_client.update_aliases(body=actions)

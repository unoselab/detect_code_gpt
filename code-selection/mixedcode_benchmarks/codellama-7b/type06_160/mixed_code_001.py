def hwc_mixed_001_01(self, expr):
        """
        Matrix multiplication printer. The sympy one turns everything into a
        dot product without type-checking.
        """
        from sympy import MatrixExpr
        links = []
        for i, j in zip(expr.args[1:], expr.args[:-1]):
            if isinstance(i, MatrixExpr) and isinstance(j, MatrixExpr):
                links.append(').dot(')
            else:
                links.append('*')
        printouts = [self._print(i) for i in expr.args]
        result = [printouts[0]]
        for link, printout in zip(links, printouts[1:]):
            result.extend([link, printout])
        return '({0})'.format(''.join(result)) 

def hwc_mixed_001_02(page, output = "text"):
    """ Extract a document page's text.

    Args:
        output: (str) text, html, dict, json, rawdict, xhtml or xml.

    Returns:
        the output of TextPage methods extractText, extractHTML, extractDICT, extractJSON, extractRAWDICT, extractXHTML or etractXML respectively. Default and misspelling choice is "text".
    """
    CheckParent(page)
    dl = page.getDisplayList()
    # available output types
    formats = ("text", "html", "json", "xml", "xhtml", "dict", "rawdict")
    # choose which of them also include images in the TextPage
    images = (0, 1, 1, 0, 1, 1, 1)      # controls image inclusion in text page
    try:
        f = formats.index(output.lower())
    except:
        f = 0
    flags = TEXT_PRESERVE_LIGATURES | TEXT_PRESERVE_WHITESPACE
    if images[f] :
        flags |= TEXT_PRESERVE_IMAGES
    tp = dl.getTextPage(flags)     # TextPage with / without images
    t = tp._extractText(f)
    del dl
    del tp
    return t 

def agc_mixed_001_03(f, id2f):
    """
    split fasta file into separate fasta files based on list of scaffolds
    that belong to each separate file
    """
    with open(f, 'r') as fh:
        for line in fh:
            if line.startswith('>'):
                id = line.strip()[1:]
                if id not in id2f:
                    id2f[id] = open(id, 'w')
                id2f[id].write(line)
            else:
                id2f[id].write(line)
    for id, fh in id2f.items():
        fh.close() 

def agc_mixed_001_04(self, course, filter_type, selected_tasks, users, aggregations, stype):
        """
        Returns the submissions that have been selected by the admin
        :param course: course
        :param filter_type: users or aggregations
        :param selected_tasks: selected tasks id
        :param users: selected usernames
        :param aggregations: selected aggregations
        :param stype: single or all submissions
        :return:
        """
        if filter_type == 'users':
            submissions = Submission.objects.filter(task__in=selected_tasks, user__in=users)
        elif filter_type == 'aggregations':
            submissions = Submission.objects.filter(task__in=selected_tasks, aggregation__in=aggregations)
        elif filter_type == 'all':
            submissions = Submission.objects.filter(task__in=selected_tasks)
        else:
            submissions = Submission.objects.none()

        if stype == 'single':
            submissions = submissions.filter(single=True)
        elif stype == 'all':
            submissions = submissions.filter(single=False)

        return submissions 

def agc_mixed_001_05():
    """
    Get the grains from the proxied device
    """
    grains = salt.salt.proxy.grains(
        __opts__,
        __grains__,
        __pillar__,
        __salt__,
        __context__,
        __proxy__,
        __file_client__,
        __env__,
        __ext_pillar__,
        __sls__,
        __top__,
        __opts__.get("id"),
        __jid__,
        __user__,
        __grains__.get("ipv6", False),
        __utils__,
        __salt_error_prefix__,
    )
    return grains 

async def hwc_mixed_001_06(self) -> None:
        """
        Explicit exit. If so configured, populate cache to prove all creds in
        wallet offline if need be, archive cache, and purge prior cache archives.

        :return: current object
        """

        LOGGER.debug('HolderProver.close >>>')

        if self.config.get('archive-holder-prover-caches-on-close', False):
            await self.load_cache_for_proof(True)
            ArchivableCaches.purge_archives(self.dir_cache, True)

        await BaseAnchor.close(self)
        for path_rr_id in Tails.links(self._dir_tails):
            rr_id = basename(path_rr_id)
            try:
                await self._sync_revoc_for_proof(rr_id)
            except ClosedPool:
                LOGGER.warning('HolderProver sync-revoc on close required ledger for %s but pool was closed', rr_id)

        LOGGER.debug('HolderProver.close <<<')

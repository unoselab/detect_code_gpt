def agc_mixed_003_01(self, entries=None):
        """ Returns names of y cat. of the IOSystem as unique names in order

        Parameters
        ----------
        entries : List, optional
            If given, retuns an list with None for all values not in entries.

        Returns
        -------
        Index
            List of categories, None if no attribute to determine
            list is available
        """
        cats = getattr(self, "y_categories", None)
        if cats is None:
            return None
        # Preserve order while removing duplicates
        uniq = list(dict.fromkeys(cats))
        if entries is None:
            return uniq
        cat_set = set(uniq)
        return [e if e in cat_set else None for e in entries] 

def hwc_mixed_003_02(start, step, axes="gca"):
    """
    This will generate a tick array and apply said array to the axis
    """
    if axes=="gca": axes = _pylab.gca()

    # first get one of the tick label locations
    yposition = axes.xaxis.get_ticklabels()[0].get_position()[1]

    # get the bounds
    xmin, xmax = axes.get_xlim()

    # get the starting tick
    nstart = int(_pylab.floor((xmin-start)/step))
    nstop  = int(_pylab.ceil((xmax-start)/step))
    ticks = []
    for n in range(nstart,nstop+1): ticks.append(start+n*step)

    axes.set_xticks(ticks)

    # set the y-position
    for t in axes.xaxis.get_ticklabels():
        x, y = t.get_position()
        t.set_position((x, yposition))

    _pylab.draw() 

def hwc_mixed_003_03(args):
    """
    %prog merge bedfiles > newbedfile

    Concatenate bed files together. Performing seqid and name changes to avoid
    conflicts in the new bed file.
    """
    p = OptionParser(merge.__doc__)
    p.set_outfile()
    opts, args = p.parse_args(args)

    if len(args) < 1:
        sys.exit(not p.print_help())

    bedfiles = args
    fw = must_open(opts.outfile, "w")
    for bedfile in bedfiles:
        bed = Bed(bedfile)
        pf = op.basename(bedfile).split(".")[0]
        for b in bed:
            b.seqid = "_".join((pf, b.seqid))
            print(b, file=fw) 

def agc_mixed_003_04(
        self, subject, message, from_email=settings.DEFAULT_FROM_EMAIL, **kwargs
    ):
        """
         Sends an email to this User.
         If settings.EMAIL_OVERRIDE_ADDRESS is set, this mail will be redirected to the alternate mail address.

        """
        from django.core.mail import send_mail
        recipient = getattr(self, "email", None)
        if not recipient:
            raise ValueError("User has no email address.")
        override = getattr(settings, "EMAIL_OVERRIDE_ADDRESS", None)
        if override:
            message = f"Original recipient: {recipient}\n\n{message}"
            recipient = override
        send_mail(subject, message, from_email, [recipient], **kwargs) 

def agc_mixed_003_05(self, user, file_obj, **metadata):
        """Add a new file.

        :returns: file handle
        """
        import uuid
        if not hasattr(self, "_files"):
            self._files = {}
        handle = str(uuid.uuid4())
        self._files[handle] = {
            "user": user,
            "file": file_obj,
            "metadata": metadata,
        }
        return handle 

def hwc_mixed_003_06(caps_str):
    """Parse list of capabilities in --capabilitylist option.

    Input string of the form: cap_name=uri,cap_name=uri
    """
    capabilities = {}
    try:
        segs = caps_str.split(',')
        for term in segs:
            (k, v) = term.split('=')
            capabilities[k] = v
    except ValueError as e:
        raise ClientFatalError(
            "Bad component of --capabilitylist option '%s' (%s)" %
            (caps_str, str(e)))
    return(capabilities)

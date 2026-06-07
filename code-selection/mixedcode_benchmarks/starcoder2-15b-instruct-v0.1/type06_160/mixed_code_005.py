def hwc_mixed_005_01(fn):
    """
    A method decorator that filters out sign_original_specals coming from models that don't
    have fields that function as ImageFieldSourceGroup sources.

    """
    @wraps(fn)
    def receiver(self, sender, **kwargs):
        # print 'inspect.isclass(sender? %s'%(inspect.isclass(sender))
        if not inspect.isclass(sender):
            return
        for src in self._source_groups:
            if issubclass(sender, src.model_class):
                fn(self, sender=sender, **kwargs)

                # If we find a match, return. We don't want to handle the signal
                # more than once.
                return
    return receiver 

def hwc_mixed_005_02(self, **kwargs):
        """
        Return pandas DataFrame with the most important results stored in the timers.
        """
        import pandas as pd
        colnames = ["fname", "wall_time", "cpu_time", "mpi_nprocs", "omp_nthreads", "mpi_rank"]

        frame = pd.DataFrame(columns=colnames)
        for i, timer in enumerate(self.timers()):
            frame = frame.append({k: getattr(timer, k) for k in colnames}, ignore_index=True)
        frame["tot_ncpus"] = frame["mpi_nprocs"] * frame["omp_nthreads"]

        # Compute parallel efficiency (use the run with min number of cpus to normalize).
        i = frame["tot_ncpus"].values.argmin()
        ref_wtime = frame.ix[i]["wall_time"]
        ref_ncpus = frame.ix[i]["tot_ncpus"]
        frame["peff"] = (ref_ncpus * ref_wtime) / (frame["wall_time"] * frame["tot_ncpus"])

        return frame 

def agc_mixed_005_03( self, ls ):
        """Internal method to generate the cross product of all parameter
        values, creating the parameter space for the experiment.

        :param ls: an array of parameter names
        :returns: list of dicts"""
        if len(ls) == 0:
            return [{}]
        else:
            result = []
            for v in self.parameters[ls[0]]:
                cp = self._crossProduct(ls[1:])
                for d in cp:
                    d[ls[0]] = v
                    result.append(d)
            return result 

def hwc_mixed_005_04(self, baseurl, filename):
        """Upload filename to this work"""
        # Prof is really dirty, we need to re-get the project page before upload
        payload = {
            'id_projet': self.field
        }
        prof_session.post(baseurl+"/main.php", params=payload)
        # We also need to get the upload page...
        payload = {
            'id': int(self.work_id)
        }
        prof_session.get(baseurl+"/upload.php", params=payload)
        # Finally we can actually send
        payload = {
            'MAX_FILE_SIZE': 1000000
        }
        prof_session.post(baseurl+'/upload2.php', files={'fichier1': open(filename, 'rb')}, params=payload) 

def agc_mixed_005_05(event):
    """
    Returns the width, height, left, and bottom of a rectangle artist.

    Parameters
    -----------
    event : PickEvent
        The pick event to process

    Returns
    --------
    A dict with keys:
        `width` : The width of the rectangle
        `height` : The height of the rectangle
        `left` : The minimum x-coordinate of the rectangle
        `right` : The maximum x-coordinate of the rectangle
        `bottom` : The minimum y-coordinate of the rectangle
        `top` : The maximum y-coordinate of the rectangle
        `xcenter` : The mean x-coordinate of the rectangle
        `ycenter` : The mean y-coordinate of the rectangle
        `label` : The label for the rectangle or None
    """
    artist = event.artist
    width = artist.get_width()
    height = artist.get_height()
    left, bottom = artist.get_xy()
    right = left + width
    top = bottom + height
    xcenter = left + width / 2
    ycenter = bottom + height / 2
    label = artist.get_label()
    return {
        'width': width,
        'height': height,
        'left': left,
        'right': right,
        'bottom': bottom,
        'top': top,
        'xcenter': xcenter,
        'ycenter': ycenter,
        'label': label,
    } 

def agc_mixed_005_06(population, fire):
    """Convert state parameters to transition probability matrix index.

    Parameters
    ----------
    population : int
        The population abundance class of the threatened species.
    fire : int
        The time in years since last fire.

    Returns
    -------
    index : int
        The index into the transition probability matrix that corresponds to
        the state parameters.

    """
    if population == 0:
        index = 0
    elif population == 1:
        index = 1
    elif population == 2:
        if fire == 0:
            index = 2
        elif fire == 1:
            index = 3
        elif fire == 2:
            index = 4
        else:
            index = 5
    else:
        index = 6

    return index

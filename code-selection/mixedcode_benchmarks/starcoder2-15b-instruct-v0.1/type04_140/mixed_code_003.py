def agc_mixed_003_01(
        self,
        input_source: str,
        output_dest: Optional[str] = None,
        extra_cmd: Optional[str] = None,
    ) -> Coroutine:
        """Open FFmpeg process for read autio stream.

        Return a coroutine.
        """
        cmd = [
            "ffmpeg",
            "-i", input_source,
        ]
        if output_dest:
            cmd += ["-f", "s16le", "-ar", "16000", "-ac", "1", output_dest]
        if extra_cmd:
            cmd += extra_cmd.split()
        return await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
        ) 

def agc_mixed_003_02(seq, k, limit=None):
    """Streaming sample.

    Iterate over seq (once!) keeping k random elements with uniform
    distribution.

    As a special case, if ``k`` is ``None``, then ``list(seq)`` is
    returned.

    :param seq: iterable of things to sample from
    :param k: size of desired sample
    :param limit: stop reading ``seq`` after considering this many
    :return: list of elements from seq, length k (or less if seq is
             short)
    """
    if k is None:
        return list(seq)

    sample = []
    for i, item in enumerate(seq):
        if limit is not None and i >= limit:
            break
        if i < k:
            sample.append(item)
        elif random.random() < k / (i + 1):
            replace = random.randint(0, k - 1)
            sample[replace] = item

    return sample 

def hwc_mixed_003_03(self, args, oui_args=None):
        """Function that runs the vdptool utility. """
        if oui_args is None:
            oui_args = []
        full_args = ['vdptool'] + args + oui_args
        try:
            return utils.execute(full_args, root_helper=self.root_helper)
        except Exception as e:
            LOG.error("Unable to execute %(cmd)s. "
                      "Exception: %(exception)s",
                      {'cmd': full_args, 'exception': e}) 

def agc_mixed_003_04(self, routers, router_name=None):
        """Returns the default router for ordering a dedicated host."""
        if not routers:
            return None
        if router_name:
            for router in routers:
                if router["name"] == router_name:
                    return router
        for router in routers:
            if router["is_default"]:
                return router
        return routers[0] 

def hwc_mixed_003_05(self):
        """
        Check whether any of the CPU cores monitored by this instance has
        throttled since this instance was created.
        @return a boolean value
        """
        for file, value in self.cpu_throttle_count.items():
            try:
                new_value = int(util.read_file(file))
                if new_value > value:
                    return True
            except Exception as e:
                logging.warning('Cannot read throttling count of CPU from kernel: %s', e)
        return False 

def hwc_mixed_003_06(self):
        """ turn fetched files into a local repo, make auxiliary files
        """
        logger.debug("preparing to add all git files")
        num_added = self.local_repo.add_all_files()
        if num_added:
            self.local_repo.commit("Initial import from Project Gutenberg")

        file_handler = NewFilesHandler(self)
        file_handler.add_new_files()

        num_added = self.local_repo.add_all_files()
        if num_added:
            self.local_repo.commit(
                "Updates Readme, contributing, license files, cover, metadata."
            )

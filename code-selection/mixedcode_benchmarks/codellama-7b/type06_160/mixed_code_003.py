def agc_mixed_003_01(self, **kwargs):
        """
        Given a set of keyword arguments, splits it into those relevant to SPI
        implementations and all the rest. SPI arguments are augmented with
        defaults and converted into the pin format (from the port/device
        format) if necessary.

        Returns a tuple of ``(spi_args, other_args)``.
        """
        spi_args = {}
        other_args = {}
        for key, value in kwargs.items():
            if key in self.spi_args:
                spi_args[key] = value
            else:
                other_args[key] = value
        for key in self.spi_args:
            if key not in spi_args:
                spi_args[key] = self.spi_args[key]
        return spi_args, other_args 

def hwc_mixed_003_02(self, prob):
        """Remove the problem from our problems list
        and check if we are still 'impacted'

        :param prob: problem to remove
        :type prob: alignak.objects.schedulingitem.SchedulingItem
        :return: None
        """
        self.source_problems.remove(prob.uuid)

        # For know if we are still an impact, maybe our dependencies
        # are not aware of the remove of the impact state because it's not ordered
        # so we can just look at if we still have some problem in our list
        if not self.source_problems:
            self.is_impact = False
            # No more an impact, we can unset the impact state
            self.unset_impact_state()

        # And we register a new broks for update status
        self.broks.append(self.get_update_status_brok()) 

def hwc_mixed_003_03(job, job_vars):
    """
    Upload bam to S3. Requires S3AM and a ~/.boto config file.
    """
    input_args, ids = job_vars
    work_dir = job.fileStore.getLocalTempDir()
    uuid = input_args['uuid']
    # I/O
    job.fileStore.readGlobalFile(ids['alignments.bam'], os.path.join(work_dir, 'alignments.bam'))
    bam_path = os.path.join(work_dir, 'alignments.bam')
    sample_name = uuid + '.bam'
    # Parse s3_dir to get bucket and s3 path
    s3_dir = input_args['s3_dir']
    bucket_name = s3_dir.split('/')[0]
    bucket_dir = os.path.join('/'.join(s3_dir.split('/')[1:]), 'bam_files')
    # Upload to S3 via S3AM
    s3am_command = ['s3am',
                    'upload',
                    'file://{}'.format(bam_path),
                    os.path.join('s3://', bucket_name, bucket_dir, sample_name)]
    subprocess.check_call(s3am_command) 

def agc_mixed_003_04(self, indices, element):
        r"""
        This is a generalized version of tomask that accepts a string of
        'pore' or 'throat' for programmatic access.
        """
        if indices is None:
            return self._tomask(self.Ps, element)
        elif isinstance(indices, str):
            if indices == 'pore':
                return self._tomask(self.Ps, element)
            elif indices == 'throat':
                return self._tomask(self.Ts, element)
            else:
                raise Exception('Invalid string')
        else:
            return self._tomask(indices, element) 

def agc_mixed_003_05(self, **kws_usr):
        """Plot one GO header group in Grouper."""
        if not self.is_grouper:
            raise ValueError("Not a Grouper.")
        if self.is_plotted:
            raise ValueError("Already plotted.")
        self.is_plotted = True
        if self.is_plt_usr:
            if self.is_plt_usr_dotstr:
                raise ValueError("Already plotted.")
            self.is_plt_usr_dotstr = True
            return self.plt_usr_dotstr
        self.is_plt_usr = True
        self.plt_usr_dotstr = self.get_pltdotstr_grouper(**kws_usr)
        return self.plt_usr_dotstr 

def hwc_mixed_003_06(self, x, sampled_values, label):
        """Forward computation."""
        sampled_candidates, _, _ = sampled_values
        # (batch_size,)
        label = label.reshape(shape=(-1,))
        # (num_sampled+batch_size,)
        ids = nd.concat(sampled_candidates, label, dim=0)
        # lookup weights and biases
        weight = self.weight.row_sparse_data(ids)
        bias = self.bias.data(ids.context)
        # (num_sampled+batch_size, dim)
        w_all = nd.Embedding(data=ids, weight=weight, **self._kwargs)
        # (num_sampled+batch_size,)
        b_all = nd.take(bias, indices=ids)
        out, new_targets = self._dense(x, sampled_values, label, w_all, b_all)
        return out, new_targets

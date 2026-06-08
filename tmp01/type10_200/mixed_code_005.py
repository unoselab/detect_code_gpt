def agc_mixed_005_01(self):
        """Check if the RPM Python binding has a depndency to popt-devel.

        Search include header files in the source code to check it.
        """
        if self.rpm_py_has_popt_devel_dep is not None:
            return self.rpm_py_has_popt_devel_dep

        self.rpm_py_has_popt_devel_dep = False
        for f in self.rpm_py_files:
            if f.endswith('.h'):
                with open(f, 'r') as fd:
                    for line in fd:
                        if 'popt.h' in line:
                            self.rpm_py_has_popt_devel_dep = True
                            break
        return self.rpm_py_has_popt_devel_dep 

def hwc_mixed_005_02(self, variable):
        """Method to parse an input or output variable.

        **Example Variable**::

        #App:1234:output!String

        Args:
            variable (string): The variable name to parse.

        Returns:
            (dictionary): Result of parsed string.
        """
        data = None
        if variable is not None:
            variable = variable.strip()
            if re.match(self._variable_match, variable):
                var = re.search(self._variable_parse, variable)
                data = {
                    'root': var.group(0),
                    'job_id': var.group(2),
                    'name': var.group(3),
                    'type': var.group(4),
                }
        return data 

def hwc_mixed_005_03(batch_id, vrn_files, config_file, base_dir, ref_file, data):
    """Run an ensemble call using merging and SVM-based approach in bcbio.variation
    """
    out_vcf_file = os.path.join(base_dir, "{0}-ensemble.vcf".format(batch_id))
    out_bed_file = os.path.join(base_dir, "{0}-callregions.bed".format(batch_id))
    work_dir = "%s-work" % os.path.splitext(out_vcf_file)[0]
    if not utils.file_exists(out_vcf_file):
        _bcbio_variation_ensemble(vrn_files, out_vcf_file, ref_file, config_file,
                                  base_dir, data)
        if not utils.file_exists(out_vcf_file):
            base_vcf = glob.glob(os.path.join(work_dir, "prep", "*-cfilter.vcf"))[0]
            utils.symlink_plus(base_vcf, out_vcf_file)
    if not utils.file_exists(out_bed_file):
        multi_beds = glob.glob(os.path.join(work_dir, "prep", "*-multicombine.bed"))
        if len(multi_beds) > 0:
            utils.symlink_plus(multi_beds[0], out_bed_file)
    return {"variantcaller": "ensemble",
            "vrn_file": out_vcf_file,
            "bed_file": out_bed_file if os.path.exists(out_bed_file) else None} 

def agc_mixed_005_04(self, model_item, data):
        """
            Merge a model with a python data structure
            This is useful to turn PUT method into a PATCH also
        :param model_item: SQLA Model
        :param data: python data structure
        :return: python data structure
        """
        if not data:
            return model_item

        if isinstance(model_item, list):
            for item in model_item:
                self._merge_update_item(item, data)
        elif isinstance(model_item, dict):
            for key, value in data.items():
                if key in model_item:
                    self._merge_update_item(model_item[key], value)
                else:
                    model_item[key] = value
        else:
            model_item.update(data)

        return model_item 

def hwc_mixed_005_05(vm_name, call=None):
    """
    Call GCE 'stop' on the instance.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop myinstance
    """
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    conn = get_conn()

    __utils__['cloud.fire_event'](
        'event',
        'stop instance',
        'salt/cloud/{0}/stopping'.format(vm_name),
        args={'name': vm_name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    result = conn.ex_stop_node(
        conn.ex_get_node(vm_name)
    )

    __utils__['cloud.fire_event'](
        'event',
        'stop instance',
        'salt/cloud/{0}/stopped'.format(vm_name),
        args={'name': vm_name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return result 

def agc_mixed_005_06(
            self,
            *,
            text: str,
    ) -> List[OutputRecord]:
        """
        Send mastodon message.

        :param text: text to send in post.
        :returns: list of output records,
            each corresponding to either a single post,
            or an error.
        """
        try:
            self.api.status_post(text)
        except MastodonIllegalArgumentError:
            return [OutputRecord(
                error=True,
                message='Text is too long.',
            )]
        except MastodonNetworkError:
            return [OutputRecord(
                error=True,
                message='Network error.',
            )]
        return [OutputRecord(
            error=False,
            message='Posted.',
        )]

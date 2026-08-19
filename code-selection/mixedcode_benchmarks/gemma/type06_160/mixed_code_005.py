def agc_mixed_005_01(package, speak=True, speakSimilar=True):
    """checks if a given package is installed on pip"""
    import pkg_resources

    try:
        pkg_resources.get_distribution(package)
        return True
    except pkg_resources.DistributionNotFound:
        if speakSimilar:
            import difflib
            installed_packages = [d.project_name for d in pkg_resources.working_set]
            similar = difflib.get_close_matches(package, installed_packages)
            if similar and speak:
                print(f"Package {package} not found. Did you mean {similar[0]}?")
        elif speak:
            print(f"Package {package} is not installed.")
        return False 

def hwc_mixed_005_02(self, text, lang):
        """ Pass a code fence through pygments """
        if lang and self._config.get('highlight_syntax', 'True'):
            try:
                lexer = pygments.lexers.get_lexer_by_name(lang, stripall=True)
            except pygments.lexers.ClassNotFound:
                lexer = None

            if lexer:
                formatter = pygments.formatters.HtmlFormatter()  # pylint: disable=no-member
                return pygments.highlight(text, lexer, formatter)

        return '\n<div class="highlight"><pre>{}</pre></div>\n'.format(
            flask.escape(text.strip())) 

def agc_mixed_005_03(self, version):
        """
        return `True` if current python version match version passed.

        raise a deprecation warning if only PY2 or PY3 is supported as you probably
        have a conditional that should be removed. 

        """

        import sys
        import warnings

        current_version = sys.version_info[:2]
        is_supported = current_version == version

        if version in ((2, 7), (3, 0)):
            warnings.warn(
                "Conditional check for a single Python version detected. "
                "This may be deprecated as the codebase evolves.",
                DeprecationWarning
            )

        return is_supported 

def hwc_mixed_005_04(classes, table, TP, TN, FP, FN, class_name):
    """
    One-Vs-All mode handler.

    :param classes: classes
    :type classes : list
    :param table: input matrix
    :type table : dict
    :param TP: true positive dict for all classes
    :type TP : dict
    :param TN: true negative dict for all classes
    :type TN : dict
    :param FP: false positive dict for all classes
    :type FP : dict
    :param FN: false negative dict for all classes
    :type FN : dict
    :param class_name : target class name for One-Vs-All mode
    :type class_name : any valid type
    :return: [classes , table ] as list
    """
    try:
        report_classes = [str(class_name), "~"]
        report_table = {str(class_name): {str(class_name): TP[class_name],
                                          "~": FN[class_name]},
                        "~": {str(class_name): FP[class_name],
                              "~": TN[class_name]}}
        return [report_classes, report_table]
    except Exception:
        return [classes, table] 

def hwc_mixed_005_05(self):
        """Return the associated resource."""
        references = {"resource_id": None, "parent_id": None,
                      "grandparent_id": None}
        for model_cls, regexp in self._regexp.iteritems():
            match = regexp.search(self.resource_ref)
            if match is not None:
                references.update(match.groupdict())
                return model_cls.get(**references)

        raise exception.NotFound("No model available for %(resource_ref)r",
                                 resource_ref=self.resource_ref) 

def agc_mixed_005_06(self, adjacent_only=True):
        """
        If this electrode contains multiple voltage steps, then it is possible
        to use only a subset of the voltage steps to define other electrodes.
        For example, an LiTiO2 electrode might contain three subelectrodes:
        [LiTiO2 --> TiO2, LiTiO2 --> Li0.5TiO2, Li0.5TiO2 --> TiO2]
        This method can be used to return all the subelectrodes with some
        options

        Args:
            adjacent_only: Only return electrodes from compounds that are
                adjacent on the convex hull, i.e. no electrodes returned
                will have multiple voltage steps if this is set true

        Returns:
            A list of ConversionElectrode objects
        """

        sub_electrodes = []
        compounds = self.compounds
        for i in range(len(compounds) - 1):
            c1 = compounds[i]
            c2 = compounds[i + 1]
            sub_electrodes.append(ConversionElectrode(c1, c2))

        if not adjacent_only:
            for i in range(len(compounds)):
                for j in range(i + 2, len(compounds)):
                    sub_electrodes.append(ConversionElectrode(compounds[i], compounds[j]))

        return sub_electrodes

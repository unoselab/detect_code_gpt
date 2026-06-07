def hwc_mixed_002_01(impact_report, component_metadata):
    """Extracting impact summary of the impact layer.

    For PDF generations

    :param impact_report: the impact report that acts as a proxy to fetch
        all the data that extractor needed
    :type impact_report: safe.report.impact_report.ImpactReport

    :param component_metadata: the component metadata. Used to obtain
        information about the component we want to render
    :type component_metadata: safe.report.report_metadata.
        ReportComponentsMetadata

    :return: context for rendering phase
    :rtype: dict

    .. versionadded:: 4.0
    """
    # QGIS Composer needed certain context to generate the output
    # - Map Settings
    # - Substitution maps
    # - Element settings, such as icon for picture file or image source

    context = QGISComposerContext()
    extra_args = component_metadata.extra_args

    html_report_component_key = resolve_from_dictionary(
        extra_args, ['html_report_component_key'])

    # we only have html elements for this
    html_frame_elements = [
        {
            'id': 'impact-report',
            'mode': 'text',
            'text': jinja2_output_as_string(
                impact_report, html_report_component_key),
            'margin_left': 10,
            'margin_top': 10,
        }
    ]
    context.html_frame_elements = html_frame_elements
    return context 

def agc_mixed_002_02(cls, orig_dir, dest_dir, roi_baseline, extracopy):
        """ Create and populate directoris for target analysis
        """
        if not os.path.exists(orig_dir):
            raise ValueError(f"Invalid directory: {orig_dir}")
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        for filename in os.listdir(orig_dir):
            if filename.endswith(roi_baseline):
                shutil.copy(os.path.join(orig_dir, filename), dest_dir)
        if extracopy:
            for filename in os.listdir(orig_dir):
                if not filename.endswith(roi_baseline):
                    shutil.copy(os.path.join(orig_dir, filename), dest_dir) 

def hwc_mixed_002_03(self, message):
        """Build inbound request object from protocol level message info.

        It is allowed to take incompleted CallRequestMessage. Therefore the
        created request may not contain whole three arguments.

        :param message: CallRequestMessage
        :return: request object
        """

        args = self.prepare_args(message)

        # TODO decide what to pass to Request from message
        req = Request(
            flags=message.flags,
            ttl=message.ttl / 1000.0,
            tracing=message.tracing,
            service=message.service,
            headers=message.headers,
            checksum=message.checksum,
            argstreams=args,
            id=message.id,
        )
        return req 

def agc_mixed_002_04(self, id, **kwargs):
        """
        Gets dependency graph for a Build Record (running or completed).

        This method makes a synchronous HTTP request by default. To make an
        asynchronous HTTP request, please define a `callback` function
        to be invoked when receiving the response.
        >>> def callback_function(response):
        >>>     pprint(response)
        >>>
        >>> thread = api.get_dependency_graph(id, callback=callback_function)

        :param callback function: The callback function
            for asynchronous request. (optional)
        :param int id: Build id. (required)
        :return: Singleton
                 If the method is called asynchronously,
                 returns the request thread.
        """
        if id is None:
            raise ValueError("Missing the required parameter `id` when calling `get_dependency_graph`")

        if id < 0:
            raise ValueError("Invalid value for parameter `id` when calling `get_dependency_graph`, must be a positive integer")

        if id > 1000000000:
            raise ValueError("Invalid value for parameter `id` when calling `get_dependency_graph`, must be less than or equal to 1000000000")

        if id % 2 == 0:
            return Singleton(id)
        else:
            return Singleton(id * 2) 

def hwc_mixed_002_05(self):
        """
        Return a matplotlib figure of the dose-response dataset.

        Examples
        --------
        >>> fig = dataset.plot()
        >>> fig.show()
        >>> fig.clear()

        .. image:: ../tests/resources/test_cidataset_plot.png
           :align: center
           :alt: Example generated BMD plot

        Returns
        -------
        out : matplotlib.figure.Figure
            A matplotlib figure representation of the dataset.
        """
        fig = plotting.create_empty_figure()
        ax = fig.gca()
        xlabel = self.kwargs.get("xlabel", "Dose")
        ylabel = self.kwargs.get("ylabel", "Response")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.scatter(
            self.individual_doses,
            self.responses,
            label="Data",
            **plotting.DATASET_INDIVIDUAL_FORMAT,
        )
        ax.margins(plotting.PLOT_MARGINS)
        ax.set_title(self._get_dataset_name())
        ax.legend(**settings.LEGEND_OPTS)
        return fig 

def agc_mixed_002_06(jsonlines, id_field, max_batch_size=CLOUDSEARCH_MAX_BATCH_SIZE):
    """Create batches in expected AWS Cloudsearch format, limiting the
    byte size per batch according to given max_batch_size

    See: http://docs.aws.amazon.com/cloudsearch/latest/developerguide/preparing-data.html
    """
    batches = []
    current_batch = []
    current_batch_size = 0

    for line in jsonlines:
        json_doc = json.loads(line)
        doc_id = json_doc[id_field]
        doc_json = json.dumps(json_doc)
        doc_size = len(doc_json)

        if current_batch_size + doc_size > max_batch_size:
            batches.append(current_batch)
            current_batch = []
            current_batch_size = 0

        current_batch.append(doc_id)
        current_batch_size += doc_size

    if current_batch:
        batches.append(current_batch)

    return batches

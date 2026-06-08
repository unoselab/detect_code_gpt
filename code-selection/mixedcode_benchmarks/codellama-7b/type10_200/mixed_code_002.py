def hwc_mixed_002_01(
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
            status = self.api.status_post(status=text)

            return [TootRecord(record_data={
                "toot_id": status["id"],
                "text": text
            })]

        except mastodon.MastodonError as e:
            return [self.handle_error((f"Bot {self.bot_name} encountered an error when "
                                      f"sending post {text} without media:\n{e}\n"),
                                     e)] 

def hwc_mixed_002_02(self, start_point, end_point):
        """Show the rectangle on the canvas.

        :param start_point: QGIS Point object representing the origin (
            top left).
        :type start_point: QgsPoint

        :param end_point: QGIS Point object representing the contra-origin (
            bottom right).
        :type end_point: QgsPoint

        :return:
        """
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        if (start_point.x() == end_point.x()
                or start_point.y() == end_point.y()):
            return

        point1 = start_point
        point2 = QgsPointXY(end_point.x(), start_point.y())
        point3 = end_point
        point4 = QgsPointXY(start_point.x(), end_point.y())

        update_canvas = False
        self.rubber_band.addPoint(point1, update_canvas)
        self.rubber_band.addPoint(point2, update_canvas)
        self.rubber_band.addPoint(point3, update_canvas)
        self.rubber_band.addPoint(point4, update_canvas)
        # noinspection PyArgumentEqualDefault
        # no False so canvas will update
        # close the polygon otherwise it shows as a filled rect
        self.rubber_band.addPoint(point1)
        self.rubber_band.show() 

def hwc_mixed_002_03(self, t: URIRef) -> Optional[URIRef]:
        """
        Return the data type for primitive type t, if any
        :param t: type
        :return: corresponding data type
        """
        for sco in self._o.objects(t, RDFS.subClassOf):
            sco_type = self._o.value(sco, RDF.type)
            sco_prop = self._o.value(sco, OWL.onProperty)
            if sco_type == OWL.Restriction and sco_prop == FHIR.value:
                # The older versions of fhir.ttl (incorrectly) referenced the datatype directly
                restriction_type = self._o.value(sco, OWL.allValuesFrom)
                if not restriction_type:
                    restriction_dt_entry = self._o.value(sco, OWL.someValuesFrom)
                    restriction_type = self._o.value(restriction_dt_entry, OWL.onDatatype)
                return restriction_type
        return None 

def agc_mixed_002_04(obj):
        """
        Remove all qualifiers from the input objectwhere the object may
        be an CIMInstance or CIMClass. Removes qualifiers from the object and
        from properties, methods, and parameters

        This is used to process the IncludeQualifier parameter for classes
        and instances
        """
        if isinstance(obj, CIMInstance):
            for p in obj.properties:
                p.qualifiers = []
        elif isinstance(obj, CIMClass):
            for p in obj.properties:
                p.qualifiers = []
            for m in obj.methods:
                m.qualifiers = []
        elif isinstance(obj, CIMParameter):
            obj.qualifiers = []
        elif isinstance(obj, CIMMethod):
            obj.qualifiers = []
        else:
            raise ValueError("Unknown object type") 

def agc_mixed_002_05(kwargs=None, conn=None, call=None):
    """
    .. versionadded:: 2015.8.0

    Return information about a management_certificate

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_management_certificate my-azure name=my_management_certificate \\
            thumbalgorithm=sha1 thumbprint=0123456789ABCDEF
    """
    if call != "function":
        raise SaltCloudSystemExit(
            "The get_management_certificate function must be called with -f or --function."
        )

    if not conn:
        conn = get_conn(**kwargs)

    thumbalgorithm = kwargs.get("thumbalgorithm", None)
    thumbprint = kwargs.get("thumbprint", None)

    if not thumbalgorithm or not thumbprint:
        raise SaltCloudSystemExit(
            "The thumbalgorithm and thumbprint arguments are required."
        )

    try:
        management_certificate = conn.get_management_certificate(
            thumbalgorithm, thumbprint
        )
    except WindowsAzureMissingCertError:
        return {"Error": "Management certificate not found."}
    except WindowsAzureError as exc:
        return {"Error": "Error getting management certificate: {}".format(exc)}

    return management_certificate 

def agc_mixed_002_06(self, current_info: AllBrainInfo, next_info: AllBrainInfo):
        """
        Checks agent histories for processing condition, and processes them as necessary.
        Processing involves calculating value and advantage targets for model updating step.
        :param current_info: Current AllBrainInfo
        :param next_info: Next AllBrainInfo
        """
        if self.replay_buffer.n_entries >= self.learning_starts:
            # Retrieve experience from the buffer
            experiences = self.replay_buffer.sample(self.batch_size)

            # Transform experiences
            states, actions, rewards, dones, last_states = self.process_experiences(experiences)

            # Calculate value targets for updated model
            next_states_value = self.get_value_targets(next_info)

            # Calculate the advantages
            self.calculate_advantages(rewards, dones, last_states, next_states_value)

            # Update the replay buffer
            self.replay_buffer.update_priorities(experiences, self.td_errors_per_sample)

            # Update the model
            self.update_model()

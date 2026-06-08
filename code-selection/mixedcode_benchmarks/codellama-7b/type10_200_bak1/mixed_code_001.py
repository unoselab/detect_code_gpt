def agc_mixed_001_01(self, current_info: AllBrainInfo, next_info: AllBrainInfo):
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

def agc_mixed_001_02(kwargs=None, conn=None, call=None):
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

def hwc_mixed_001_03(self):
        """Return a list of attribute names for the mapping.

        :rtype: list

        """
        return sorted([k for k in dir(self) if
                       k[0:1] != '_' and k != 'keys' and not k.isupper() and
                       not inspect.ismethod(getattr(self, k)) and
                       not (hasattr(self.__class__, k) and
                            isinstance(getattr(self.__class__, k),
                                       property)) and
                       not isinstance(getattr(self, k), property)]) 

def hwc_mixed_001_04(self, event):
        """
        Callback for the B1-Motion event, or the dragging of an item.

        Moves the item to the desired location, but limits its movement to a
        place on the actual Canvas. The item cannot be moved outside of the Canvas.

        :param event: Tkinter event
        """
        self.set_current()
        results = self.canvas.find_withtag(tk.CURRENT)
        if len(results) is 0:
            return
        item = results[0]
        rectangle = self.items[item]
        self.config(cursor="exchange")
        self.canvas.itemconfigure(item, fill="blue")
        xc, yc = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        dx, dy = xc - self.current_coords[0], yc - self.current_coords[1]
        self.current_coords = xc, yc
        self.canvas.move(item, dx, dy)
        # check whether the new position of the item respects the boundaries
        x, y = self.canvas.coords(item)
        x, y = max(min(x, self._max_x), 0), max(min(y, self._max_y), 0)
        self.canvas.coords(item, x, y)
        self.canvas.coords(rectangle, self.canvas.bbox(item)) 

def agc_mixed_001_05(obj):
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

def hwc_mixed_001_06(self, request, pk=None):
        """
        fetch large object from pg and gives it back to user via HTTP 1.1
        request

        :param request: django request instance
        :param pk: requested resource primary key
        :rtype: django.http.HttpResponse
        :rtype: HttpResponse
        :return: file with its filename stored in database
        """
        obj = self.get_object_or_none()
        if obj:
            blob = obj.get_blob_data()
            content_type = 'octet/stream'
            response = HttpResponse(blob, content_type=content_type,
                                    status=status.HTTP_200_OK)
            response['Content-Disposition'] = (
                'attachment; filename="%s"' % obj.name
            )
            return response
        return HttpResponse('404', status=status.HTTP_404_NOT_FOUND,
                            content_type='application/json')

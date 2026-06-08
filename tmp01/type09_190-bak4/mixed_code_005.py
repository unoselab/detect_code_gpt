def hwc_mixed_005_01(self):
        """ Return handler capture statistics

        Return a dictionary of capture handler statistics of the form:

        .. code-block:: none

            [{
                'name': The handler's name,

                'reads': The number of packet reads this handler has received

                'data_read_length': The total length of the data received

                'approx_data_rate': The approximate data rate for this handler
            }, ...]

        """
        stats = []
        for h in self.capture_handlers:
            now = calendar.timegm(time.gmtime())
            rot_time = calendar.timegm(h['log_rot_time'])
            time_delta = now - rot_time
            approx_data_rate = '{} bytes/second'.format(h['data_read'] / float(time_delta))

            stats.append({
                'name': h['name'],
                'reads': h['reads'],
                'data_read_length': '{} bytes'.format(h['data_read']),
                'approx_data_rate': approx_data_rate
            })

        return stats 

async def agc_mixed_005_02(self, status, avatar=None):
        """Generate a discord status icon below the image provided.

        This function is a coroutine.

        Parameters:
            status: str - a discord status, must be online, idle, dnd, or streaming
            avatar: str - http/s url pointing to an avatar, has to have proper headers and be a direct link to an image
                    (Note, this url is encoded by the wrapper itself, so you don't have to worry about encoding it ;))

        Return Type: image data"""
        if status not in ("online", "idle", "dnd", "streaming"):
            raise ValueError("Invalid status provided.")
        if avatar is not None:
            if not avatar.startswith(("http://", "https://")):
                raise ValueError("Invalid avatar URL provided.")
            if not self.is_image_url(avatar):
                raise ValueError("Invalid avatar URL provided.")
        status_image = Image.open(f"path/to/status_{status}.png")
        if avatar is not None:
            avatar_image = Image.open(urllib.request.urlopen(avatar))
            avatar_image = avatar_image.resize((32, 32))
            status_image.paste(avatar_image, (16, 16))
        return status_image 

def agc_mixed_005_03(self):
        """Create a property dict that is used to recreate an edge dictionary for a :class:`BELGraph`.

        :return: Property dictionary of an edge that is participant (sub/obj) related.
        :rtype: dict
        """
        return {
            "subject": self.subject,
            "object": self.object,
            "relation": self.relation,
            "name": self.name,
            "namespace": self.namespace,
            "identifier": self.identifier,
            "resource": self.resource,
            "variant": self.variant,
            "location": self.location,
            "evidence": self.evidence,
            "annotations": self.annotations,
            "citation": self.citation,
            "support": self.support,
        } 

def hwc_mixed_005_04(self):
        """
        Flatten out all top level interfaces and only return sub interfaces.
        It is recommended to use :meth:`~all_interfaces`, :meth:`~interfaces`
        or :meth:`~vlan_interfaces` which return collections with helper
        methods to get sub interfaces based on index or attribute value pairs.

        :rtype: list(SubInterface)
        """
        interfaces = self.all_interfaces
        sub_interfaces = []
        for interface in interfaces:
            if isinstance(interface, VlanInterface):
                if interface.has_interfaces:
                    for subaddr in interface.interfaces:
                        sub_interfaces.append(subaddr)
                else:
                    sub_interfaces.append(interface)
            else:
                sub_interfaces.append(interface)

        return sub_interfaces 

def agc_mixed_005_05(self):
        """
        There's only about 30 environments in which the phenotypes
        are recorded.
        There are no externally accessible identifiers for environments,
        so we make anonymous nodes for now.
        Some of the environments are comprised of >1 of the other environments;
        we do some simple parsing to match the strings of the environmental
        labels to the other atomic components.

        :return:

        """
        environments = {}
        for environment in self.phenotypes["Environment"]:
            if "+" in environment:
                sub_environments = environment.split("+")
                for sub_environment in sub_environments:
                    if sub_environment not in environments:
                        environments[sub_environment] = []
                    environments[sub_environment].append(environment)
            else:
                environments[environment] = []
        return environments 

def hwc_mixed_005_06(self, docsrc, from_page=-1, to_page=-1, start_at=-1, rotate=-1, links=1):
        """Copy page range ['from', 'to'] of source PDF, starting as page number 'start_at'."""
        if self.isClosed or self.isEncrypted:
            raise ValueError("operation illegal for closed / encrypted doc")
        if id(self) == id(docsrc):
            raise ValueError("source must not equal target PDF")
        sa = start_at
        if sa < 0:
            sa = self.pageCount

        val = _fitz.Document_insertPDF(self, docsrc, from_page, to_page, start_at, rotate, links)
        self._reset_page_refs()
        if links:
            self._do_links(docsrc, from_page = from_page, to_page = to_page,
                           start_at = sa)

        return val

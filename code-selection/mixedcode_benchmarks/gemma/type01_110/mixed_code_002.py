async def agc_mixed_002_01(service, action_type, payload, props, **kwds):
    """
        This query handler builds the dynamic picture of availible services.
    """
    # if the action represents a new service
    context = {
        "service": service,
        "action": action_type,
        "payload": payload,
        "props": props,
        **kwds
    }
    try:
        result = await service.execute(action_type, payload, **props)
        return {"status": "success", "data": result, "context": context}
    except Exception as e:
        return {"status": "error", "message": str(e), "context": context} 

async def hwc_mixed_002_02(self, offer_urls):
        """
        offer_urls : typing.Sequence[str]
        Returns -> typing.Sequence[~RemoteApplicationInfoResult]
        """
        # map input types to rpc msg
        _params = dict()
        msg = dict(type='ApplicationOffers',
                   request='RemoteApplicationInfo',
                   version=2,
                   params=_params)
        _params['offer-urls'] = offer_urls
        reply = await self.rpc(msg)
        return reply 

def agc_mixed_002_03(self, req=None, resp=None, **kwargs):
        """Extend default endpoint description with serializer description."""
        description = kwargs.get('description', '')
        serializer = getattr(self, 'serializer_class', None)
        if serializer:
            serializer_desc = getattr(serializer, 'description', '')
            if serializer_desc:
                description = f"{description}\n\n{serializer_desc}".strip()
        kwargs['description'] = description
        return super().describe(req, resp, **kwargs) 

def hwc_mixed_002_04(self):
        """Returns the longest length of the variant. For deletions, return is negative,
        SNPs return 0, and insertions are +. None return corresponds to no variant in interval
        for specified individual

        """
        #this is a hack to store the # of individuals without having to actually store it
        out = []
        for i in six.moves.range(len(self.genotype)):
            valid_alt = self.get_alt_length(individual=i)
            if not valid_alt:
                out.append(None)
            else:
                out.append(max(valid_alt)-len(self.ref))
        return out 

def agc_mixed_002_05(source, target):
    """
    Copy any VPCS configs to the converted topology

    :param str source: Source topology directory
    :param str target: Target topology files directory
    """
    # Prepare a list of files to copy
    import os
    import shutil

    source_vpcs = os.path.join(source, 'vpcs')
    target_vpcs = os.path.join(target, 'vpcs')

    if os.path.exists(source_vpcs):
        if not os.path.exists(target_vpcs):
            os.makedirs(target_vpcs)
        for filename in os.listdir(source_vpcs):
            shutil.copy2(os.path.join(source_vpcs, filename),
                         os.path.join(target_vpcs, filename)) 

def hwc_mixed_002_06(self, message):
        """
        Formatted Message to send to Polyglot. Connection messages are sent automatically from this module
        so this method is used to send commands to/from Polyglot and formats it for consumption
        """
        if not isinstance(message, dict) and self.connected:
            warnings.warn('payload not a dictionary')
            return False
        try:
            message['node'] = self.profileNum
            self._mqttc.publish(self.topicInput, json.dumps(message), retain=False)
        except TypeError as err:
            LOGGER.error('MQTT Send Error: {}'.format(err), exc_info=True)

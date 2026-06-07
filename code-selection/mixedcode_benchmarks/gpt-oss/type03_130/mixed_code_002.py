async def agc_mixed_002_01(self, references):
        """
        references : typing.Sequence[str]
        Returns -> typing.Sequence[~ResolveCharmResult]
        """
        # map input types to rpc msg
        import asyncio
        if not isinstance(references, (list, tuple)):
            raise TypeError("references must be a sequence of strings")
        for ref in references:
            if not isinstance(ref, str):
                raise TypeError("each reference must be a string")
        coroutines = [self.ResolveCharm(ref) for ref in references]
        results = await asyncio.gather(*coroutines, return_exceptions=False)
        return results 

def hwc_mixed_002_02(self, message_type, data, callback=None, one_way=False):
        """Sends a message of message_type

        Args:
            message_type (validator_pb2.Message): enum value
            data (bytes): serialized protobuf
            callback (function): a callback function to call when a
                response to this message is received

        Returns:
            future.Future
        """
        message = validator_pb2.Message(
            correlation_id=_generate_id(),
            content=data,
            message_type=message_type)

        fut = future.Future(message.correlation_id, message.content,
                            callback, timeout=self._connection_timeout)
        if not one_way:
            self._futures.put(fut)

        self._send_receive_thread.send_message(message)
        return fut 

def hwc_mixed_002_03(self, superclass, namespace=None,
                   local_only=False, include_qualifiers=True,
                   include_classorigin=True):
        """
        This method is just rename of GetClass to support same method
        with both MOFWBEMConnection and FakedWBEMConnection
        """
        return self.GetClass(superclass,
                             namespace=namespace,
                             local_only=local_only,
                             include_qualifiers=include_qualifiers,
                             include_classorigin=include_classorigin) 

def hwc_mixed_002_04(self):
        """
        Draws the alphas values against their associated error in a similar
        fashion to the AlphaSelection visualizer.
        """
        # Plot the alpha against the error
        self.ax.plot(self.alphas, self.errors, label=self.name.lower())

        # Draw a dashed vline at the alpha with maximal error
        alpha = self.alphas[np.where(self.errors == self.errors.max())][0]
        label = "$\\alpha_{{max}}={:0.3f}$".format(alpha)
        self.ax.axvline(alpha, color='k', linestyle='dashed', label=label)

        # Draw a dashed vline at the alpha with minimal error
        alpha = self.alphas[np.where(self.errors == self.errors.min())][0]
        label = "$\\alpha_{{min}}={:0.3f}$".format(alpha)
        self.ax.axvline(alpha, color='k', linestyle='dashed', label=label)

        return self.ax 

def agc_mixed_002_05(orientations, *groups, **kwargs):
    """
    Create groups of an orientation measurement dataset
    """
    import pandas as pd

    if not isinstance(orientations, pd.DataFrame):
        raise TypeError("orientations must be a pandas DataFrame")

    # Determine grouping keys
    group_keys = list(groups) if groups else None

    # No grouping requested: return the whole dataset as a single group
    if not group_keys:
        return {"all": orientations.copy()}

    # Perform the grouping
    grouped = orientations.groupby(group_keys, **{k: v for k, v in kwargs.items() if k not in {"as_dict", "reset_index"}})

    # Build result container
    as_dict = kwargs.get("as_dict", True)
    reset 

def agc_mixed_002_06(uri: URIRef) -> str:
        """
        Convert a FHIR style URI into a tag name to be used to retrieve data from a JSON representation
        Example: http://hl7.org/fhir/Provenance.agent.whoReference --> whoReference
        :param uri: URI to convert
        :return: tag name
        """
        s = str(uri)
        # Remove query parameters
        s = s.split('?', 1)[0]
        # Use fragment if present
        if '#' in s:
            s = s.split('#')[-1]
        # Get the part after the last slash
        tail = s.rsplit('/', 1)[-1]
        # Return the segment after the last dot, or the whole tail if no dot
        return tail.rsplit('.', 1)[-1]

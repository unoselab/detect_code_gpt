def agc_mixed_001_01(self):
        """Apply changes callback"""
        for change in self.changes:
            if change.action == 'add':
                self.add(change.item)
            elif change.action =='remove':
                self.remove(change.item)
            elif change.action == 'update':
                self.update(change.item) 

def hwc_mixed_001_02(self):
        """
        Return ``True`` if the container can be safely extracted,
        that is, if all its entries are safe, ``False`` otherwise.

        :rtype: bool
        :raises: same as :func:`~aeneas.container.Container.entries`
        """
        self.log(u"Checking if this container is safe")
        for entry in self.entries:
            if not self.is_entry_safe(entry):
                self.log([u"This container is not safe: found unsafe entry '%s'", entry])
                return False
        self.log(u"This container is safe")
        return True 

def hwc_mixed_001_03(self, assetId, fixed8_val):
        """
        Add amount to the specified balance.

        Args:
            assetId (UInt256):
            fixed8_val (Fixed8): amount to add.
        """
        found = False
        for key, balance in self.Balances.items():
            if key == assetId:
                self.Balances[assetId] = self.Balances[assetId] + fixed8_val
                found = True
        if not found:
            self.Balances[assetId] = fixed8_val 

def agc_mixed_001_04(self, pattern: Union[Pattern, FlatTerm], final_label: T=None) -> int:
        """Add a pattern to the discrimination net.

        Args:
            pattern:
                The pattern which is added to the DiscriminationNet. If an expression is given, it will be converted to
                a `FlatTerm` for internal processing. You can also pass a `FlatTerm` directly.
            final_label:
                A label that is returned if the pattern matches when using :meth:`match`. This will default to the
                pattern itself.

        Returns:
            The index of the newly added pattern. This is used internally to later to get the pattern and its final
            label once a match is found.
        """
        if isinstance(pattern, Pattern):
            flat_term = FlatTerm(pattern.findall(''), final_label or pattern)
        elif isinstance(pattern, FlatTerm):
            flat_term = pattern
        else:
            raise TypeError('Pattern must be a Pattern or FlatTerm')

        self.patterns.append(flat_term)
        self.final_labels.append(flat_term.final_label)

        return len(self.patterns) - 1 

def hwc_mixed_001_05(self, event):
        """Handles closing of the window. If configs were edited, ask user to continue.

        :param event: the close event
        :type event: QCloseEvent
        :returns: None
        :rtype: None
        :raises: None
        """
        if self.inimodel.get_edited():
            r = self.doc_modified_prompt()
            if r == QtGui.QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept() 

def agc_mixed_001_06(self, assessment_taken_query):
        """Gets a list of ``AssessmentTaken`` elements matching the given assessment taken query.

        arg:    assessment_taken_query
                (osid.assessment.AssessmentTakenQuery): the assessment
                taken query
        return: (osid.assessment.AssessmentTakenList) - the returned
                ``AssessmentTakenList``
        raise:  NullArgument - ``assessment_taken_query`` is ``null``
        raise:  OperationFailed - unable to complete request
        raise:  PermissionDenied - authorization failure occurred
        raise:  Unsupported - ``assessment_taken_query`` is not of this
                service
        *compliance: mandatory -- This method must be implemented.*

        """
        # Implemented from template for
        # osid.resource.ResourceQuerySession.get_resources_by_query
        if assessment_taken_query is None:
            raise NullArgument()
        if not isinstance(assessment_taken_query, AssessmentTakenQuery):
            raise Unsupported()
        assessments_taken = []
        for assessment_taken in self._assessments_taken:
            if assessment_taken_query.match_assessment_taken(assessment_taken):
                assessments_taken.append(assessment_taken)
        return AssessmentTakenList(assessments_taken)

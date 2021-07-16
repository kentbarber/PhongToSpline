"""
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import c4d
from c4d import utils   

ID_PHONGTOSPLINE = 1056130

ID_PHONGTOSPLINE_SELECTION = 1000
ID_PHONGTOSPLINE_INPUTLINK = 1001
ID_PHONGTOSPLINE_SPLINETYPE = 1002
ID_PHONGTOSPLINE_LINEAR = 0
ID_PHONGTOSPLINE_AKIMA = 1
ID_PHONGTOSPLINE_BSPLINE = 2
ID_PHONGTOSPLINE_SUBDIVISIONS = 1003
ID_PHONGTOSPLINE_OVERRIDETYPE = 1004
ID_PHONGTOSPLINE_ISOPARMMODE = 1005
ID_PHONGTOSPLINE_CLOSE = 1006

def CheckSelfReferencing(startObject, op):
    objectStack = []
    objectStack.append(startObject)

    firstObject = True

    while objectStack:
        currentObject = objectStack.pop()
        if currentObject == op:
            return True

        downObject = currentObject.GetDown()
        if downObject is not None:
            objectStack.append(downObject)

        if not firstObject:
            nextObject = currentObject.GetNext()
            if nextObject is not None:
                objectStack.append(nextObject)
        
        firstObject = False
        
    return False

def CollectIsoParms(startObject, op, ignoreFirst, doc):
    objList = []
    objectStack = []
    objectStack.append(startObject)
    firstObject = True
    closed = op[ID_PHONGTOSPLINE_CLOSE]
    while objectStack:
        currentObject = objectStack.pop()
        isGenerator = currentObject.GetInfo() & c4d.OBJECT_GENERATOR == c4d.OBJECT_GENERATOR
        isInputGenerator = isGenerator and currentObject.GetInfo() & c4d.OBJECT_INPUT == c4d.OBJECT_INPUT

        if not isInputGenerator:
            downObject = currentObject.GetDown()
            if downObject is not None and downObject != op:
                objectStack.append(downObject)

        if not firstObject:
            nextObject = currentObject.GetNext()
            if nextObject is not None and nextObject != op:
                objectStack.append(nextObject)

        if ignoreFirst and firstObject:
            firstObject = False
            continue

        isoParmLine = currentObject.GetIsoparm()
        matrix = currentObject.GetMg()

        if isoParmLine is not None or currentObject.GetInfo() & c4d.OBJECT_GENERATOR == c4d.OBJECT_GENERATOR and currentObject.GetCache():
            if isoParmLine is None:
                isoParmLine = currentObject.GetCache().GetIsoparm()
                matrix = currentObject.GetCache().GetMg()

            if isoParmLine is None:
                # trigger isoparm generation in new document
                tempDoc = c4d.documents.BaseDocument()
                clone = currentObject.GetClone(c4d.COPYFLAGS_NONE)
                clone.SetMg(currentObject.GetMg())
                tempDoc.InsertObject(clone)
                tempDoc.SetTime(doc.GetTime())
                tempDoc.ExecutePasses(None, False, False, True, c4d.BUILDFLAGS_ISOPARM)
                cacheObject = tempDoc.GetFirstObject().GetCache()
                if cacheObject is not None:
                    
                    isoParmLine = cacheObject.GetIsoparm()
                    matrix = cacheObject.GetMg()
                    if isoParmLine is None:
                        objectStack.append(cacheObject)

            if isoParmLine is not None:
                spline = c4d.SplineObject(isoParmLine.GetPointCount(), c4d.SPLINETYPE_LINEAR)
                spline.ResizeObject(isoParmLine.GetPointCount(), isoParmLine.GetSegmentCount())
                segmentTag = isoParmLine.GetTag(c4d.Tsegment)
                closedSegments = 0
                mixedState = False
                if segmentTag is not None:
                    segData = segmentTag.GetAllHighlevelData()
                    segmentsClosed = False
                    firstSegment = True
                    for segment in segData:
                        if segment["closed"] == True:
                            closedSegments = closedSegments + 1

                        if firstSegment:
                            segmentsClosed = segment["closed"]
 
                        else:
                            if segment["closed"] != segmentsClosed:
                                segmentsClosed = closed
                                mixedState = True

                        firstSegment = False

                    spline[c4d.SPLINEOBJECT_CLOSED] = segmentsClosed
                    segmentTag.CopyTo(spline.GetTag(c4d.Tsegment), c4d.COPYFLAGS_NONE)
                
                if mixedState == True:
                    spline[c4d.SPLINEOBJECT_CLOSED] = closed
                    if not closed:
                        spline.ResizeObject(isoParmLine.GetPointCount() + closedSegments, isoParmLine.GetSegmentCount())

                        sourceIndex = 0
                        targetIndex = 0
                        segmentTagTarget = spline.GetTag(c4d.Tsegment)
                        if segmentTagTarget is not None:
                            segDataSpline = segmentTagTarget.GetAllHighlevelData()
                            segDataWritable = segmentTagTarget.GetLowlevelDataAddressW()
                            segDataSize = segmentTagTarget.GetDataSize()
                            segmentIndex = 0
                            for segment in segDataSpline:
                                segmentStart = targetIndex
                                segmentCount = segment["cnt"]
                                for indexOffset in range(segmentCount):
                                    spline.SetPoint(segmentStart + indexOffset, isoParmLine.GetPoint(sourceIndex + indexOffset))
                                
                                if segment["closed"] == True:
                                    if segDataWritable is not None:
                                        byteShift = 0
                                        while byteShift < 4 and segDataWritable[segmentIndex * segDataSize + byteShift] is 255:
                                            segDataWritable[segmentIndex * segDataSize + byteShift] = 0
                                            byteShift = byteShift + 1

                                        segDataWritable[segmentIndex * segDataSize + byteShift] = segDataWritable[segmentIndex * segDataSize + byteShift] + 1

                                    spline.SetPoint(segmentStart + segmentCount, isoParmLine.GetPoint(sourceIndex))
                                    targetIndex = targetIndex + 1
                                
                                targetIndex = targetIndex + segmentCount
                                sourceIndex = sourceIndex + segmentCount
                                segmentIndex = segmentIndex + 1
                    else:
                        spline.SetAllPoints(isoParmLine.GetAllPoints())
                            
                else:
                    spline.SetAllPoints(isoParmLine.GetAllPoints())

                spline.SetMg(matrix)
                objList.append(spline)

        firstObject = False
    return objList

def CollectChildDirty(startObject, op, ignoreFirst):
    objectStack = []
    objectStack.append(startObject)

    firstObject = True
    dirtyCount = 0
    while objectStack:
        currentObject = objectStack.pop()

        downObject = currentObject.GetDown()
        if downObject is not None and downObject != op:
            objectStack.append(downObject)

        if not firstObject:
            nextObject = currentObject.GetNext()
            if nextObject is not None and nextObject != op:
                objectStack.append(nextObject)

        if ignoreFirst and firstObject:
            firstObject = False
            continue

        dirtyCount += currentObject.GetDirty(c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX | c4d.DIRTYFLAGS_CACHE)

        firstObject = False
    return dirtyCount

def CollectPolygonObjects(startObject, op, ignoreFirst):
    polyList = []
    objectStack = []
    objectStack.append(startObject)

    firstObject = True

    while objectStack:
        currentObject = objectStack.pop()

        downObject = currentObject.GetDown()
        if downObject is not None and downObject != op:
            objectStack.append(downObject)

        if not firstObject:
            nextObject = currentObject.GetNext()
            if nextObject is not None and nextObject != op:
                objectStack.append(nextObject)

        if ignoreFirst and firstObject:
            firstObject = False
            continue

        if currentObject.GetCache():
            objectStack.append(currentObject.GetCache())

        if currentObject.IsInstanceOf(c4d.Opolygon):
            if currentObject.GetDeformCache() is not None:
                currentObject = currentObject.GetDeformCache()

            if not currentObject.GetBit(c4d.BIT_CONTROLOBJECT) and currentObject.GetPolygonCount() > 0:
                objectCopy = currentObject.GetClone(c4d.COPYFLAGS_NO_HIERARCHY | c4d.COPYFLAGS_NO_ANIMATION | c4d.COPYFLAGS_NO_BITS)
                objectCopy.SetMg(currentObject.GetMg())
                polyList.append(objectCopy)

        firstObject = False
        
    return polyList

def GetPolyIndex(poly, index):
    if index == 0:
        return poly.a
    if index == 1:
        return poly.b
    if index == 2:
        return poly.c
    
    return poly.d

def CreatePhongBreak(polyObj):
    phongBreakSel = c4d.BaseSelect();

    normals = polyObj.CreatePhongNormals()
    neighbor = c4d.utils.Neighbor()
    neighbor.Init(polyObj)
    processed = set()
    polygonCount = polyObj.GetPolygonCount()
     
    if normals is not None:
        for polyIndex in range(polygonCount):
            poly = polyObj.GetPolygon(polyIndex)
            polyOffset = polyIndex * 4
            count = 4
            if poly.IsTriangle():
                count = 3
            
            for curIndex in range(count):
                nextIndex = curIndex + 1
                if nextIndex == count:
                    nextIndex = 0

                pointIndexOne = GetPolyIndex(poly, curIndex)
                pointIndexTwo = GetPolyIndex(poly, nextIndex)
                if (pointIndexOne, pointIndexTwo) not in processed:
                    # process edge
                    neighborIndex = neighbor.GetNeighbor(pointIndexOne, pointIndexTwo, polyIndex)
                    if neighborIndex != -1:
                        neighborPoly = polyObj.GetPolygon(neighborIndex)
                        neighborOffset = neighborIndex * 4
                        normalIndexOne = polyOffset + curIndex
                        normalIndexTwo = polyOffset + nextIndex

                        normalIndexNeighborOne = neighborOffset + neighborPoly.Find(pointIndexOne)
                        normalIndexNeighborTwo = neighborOffset + neighborPoly.Find(pointIndexTwo)
                        if normals[normalIndexOne] != normals[normalIndexNeighborOne] and normals[normalIndexTwo] != normals[normalIndexNeighborTwo]:
                            phongBreakSel.Select(normalIndexOne)
                            phongBreakSel.Select(normalIndexNeighborTwo)
                        processed.add((pointIndexOne, pointIndexTwo))
                        processed.add((pointIndexTwo, pointIndexOne))
    return phongBreakSel

def ProcessEdgeSelection(polyObj, selectionName):

    finalSelection = CreatePhongBreak(polyObj)
    sel = finalSelection.GetAll(polyObj.GetPolygonCount() * 4)

    if selectionName is not None and selectionName != "":
        tagObj = polyObj.GetFirstTag()

        while tagObj:
            if tagObj.GetName() == selectionName:
                if tagObj.IsInstanceOf(c4d.Tedgeselection):
                    baseSelectNew = tagObj.GetBaseSelect()
                    for index, selected in enumerate(sel):
                        if not selected: continue
                        if not baseSelectNew.IsSelected(index):
                            finalSelection.Deselect(index)
                    break

                elif tagObj.IsInstanceOf(c4d.Tpolygonselection):
                    # reduce the phong break to only these polygon indices
                    baseSelectNew = tagObj.GetBaseSelect()

                    for index, selected in enumerate(sel):
                        polyIndex = index / 4
                        if not baseSelectNew.IsSelected(polyIndex):
                            finalSelection.Deselect(index)

                    break
            tagObj = tagObj.GetNext()

    targetEdgeSel = polyObj.GetEdgeS()
    targetEdgeSel.DeselectAll()
    sel = finalSelection.GetAll(polyObj.GetPolygonCount() * 4)
    for index, selected in enumerate(sel):
        if not selected: continue
        targetEdgeSel.Select(index)

    if polyObj.GetNgonCount() > 0:
        # remove all internal ngon edges
        ngonEdges = polyObj.GetNgonEdgesCompact()
        for polyIndex, entry in enumerate(ngonEdges):
            if entry == 0:
                continue
            else:
                for edgeIndex in range(4): 
                    if entry & (1 << edgeIndex) != 0:
                        finalSelection.Deselect(polyIndex * 4 + edgeIndex)

def TransferSplineMode(targetSpline, op):
    type = op[ID_PHONGTOSPLINE_SPLINETYPE]
    subdivisions = op[ID_PHONGTOSPLINE_SUBDIVISIONS]

    if type == ID_PHONGTOSPLINE_LINEAR:
        targetSpline[c4d.SPLINEOBJECT_TYPE] = c4d.SPLINEOBJECT_TYPE_LINEAR
    elif type == ID_PHONGTOSPLINE_AKIMA:
        targetSpline[c4d.SPLINEOBJECT_TYPE] = c4d.SPLINEOBJECT_TYPE_AKIMA
    elif type == ID_PHONGTOSPLINE_BSPLINE:
        targetSpline[c4d.SPLINEOBJECT_TYPE] = c4d.SPLINEOBJECT_TYPE_BSPLINE

    targetSpline[c4d.SPLINEOBJECT_INTERPOLATION] = c4d.SPLINEOBJECT_INTERPOLATION_UNIFORM
    targetSpline[c4d.SPLINEOBJECT_SUB] = subdivisions

def OptimizeSpline(splineObj):
    """detect if all segments of this spline are closed by having the same start and end point"""
    """if that is the case, remove the end point and set the spline to be closed instead"""
    segmentTag = splineObj.GetTag(c4d.Tsegment)
    closedSegments = 0
    if segmentTag is not None:
        segData = segmentTag.GetAllHighlevelData()
        segmentStart = 0
        # first check if we cann optimize the spline
        for segment in segData:
            segmentCount = segment["cnt"]
            if segmentCount > 2:
                if (splineObj.GetPoint(segmentStart) - splineObj.GetPoint(segmentStart + segmentCount - 1)).GetLengthSquared() > 0.00001:
                    # at least one segment cannot be closed without large error, so the spline is not optimized into an closed loop
                    return

            segmentStart = segmentStart + segmentCount
            
        # remove all endpoint of each segment and shift the points
        points = splineObj.GetAllPoints()
        splineObj.ResizeObject(splineObj.GetPointCount() - len(segData), splineObj.GetSegmentCount())
        
        segDataWritable = segmentTag.GetLowlevelDataAddressW()
        segDataSize = segmentTag.GetDataSize()

        segmentIndex = 0
        pointIndex = 0
        for segment in segData:
            segmentCount = segment["cnt"]

            # override segmentpoints except the last point
            # targetindex is the pointindex minus the segmentindex, because those are the previously removed points
            for indexOffset in range(segmentCount - 1):
                splineObj.SetPoint(pointIndex - segmentIndex + indexOffset, points[pointIndex + indexOffset])

            # reduce the segment pointcount by one
            if segDataWritable is not None:
                byteShift = 0
                # because these are bytes, byteshifts need to be done manually on decrement (honestly :D)
                while byteShift < 4 and segDataWritable[segmentIndex * segDataSize + byteShift] is 0:
                    segDataWritable[segmentIndex * segDataSize + byteShift] = 255
                    byteShift = byteShift + 1

                segDataWritable[segmentIndex * segDataSize + byteShift] = segDataWritable[segmentIndex * segDataSize + byteShift] - 1


            pointIndex = pointIndex + segmentCount
            segmentIndex = segmentIndex + 1
        
        splineObj[c4d.SPLINEOBJECT_CLOSED] = True

class PhongToSplineObjectData(c4d.plugins.ObjectData):

    def __init__(self):
        self.inputLinkMatrixDirty = 0
        self.selfDirtyCount = 0
        self.prevChildDirty = 0

    def Init(self, node):
        node[ID_PHONGTOSPLINE_SELECTION] = ""
        node[ID_PHONGTOSPLINE_SPLINETYPE] = ID_PHONGTOSPLINE_LINEAR
        node[ID_PHONGTOSPLINE_SUBDIVISIONS] = 0
        node[ID_PHONGTOSPLINE_OVERRIDETYPE] = False
        node[ID_PHONGTOSPLINE_CLOSE] = False
        node[ID_PHONGTOSPLINE_ISOPARMMODE] = False
        return True

    def CreateSplineFromPolyEdges(self, startObject, edgeSelectionName, op, ignoreFirst):
        splineOutputs = []
        settings = c4d.BaseContainer()
        if op[ID_PHONGTOSPLINE_ISOPARMMODE]:
            splineOutputs = CollectIsoParms(startObject, op, ignoreFirst, op.GetDocument())
        else:
            polyObjectList = CollectPolygonObjects(startObject, op, ignoreFirst)
            if len(polyObjectList) == 0:
                return None
            # call edge to spline modeling command
            for polyObj in polyObjectList:
                ProcessEdgeSelection(polyObj, edgeSelectionName)

                res = utils.SendModelingCommand(command=c4d.MCOMMAND_EDGE_TO_SPLINE,
                                    list=[polyObj],
                                    mode=c4d.MODELINGCOMMANDMODE_EDGESELECTION,
                                    bc=settings,
                                    doc=None)
                if res is True:
                    splineObj = polyObj.GetDown()
                    if splineObj != None:
                        splineObj.Remove()
                        splineObj.SetMg(polyObj.GetMg())
                        OptimizeSpline(splineObj)
                        splineOutputs.append(splineObj)

        if len(splineOutputs) == 0:
            return None

        returnObject = None

        # join the splines if multiple input objects were found
        if len(splineOutputs) > 1:
            doc = op.GetDocument()
            tempdoc = c4d.documents.BaseDocument()
            
            for spline in splineOutputs:
                tempdoc.InsertObject(spline)

            settings[c4d.MDATA_JOIN_MERGE_SELTAGS] = True
            res = utils.SendModelingCommand(command=c4d.MCOMMAND_JOIN,
                                list=splineOutputs,
                                mode=1032176,
                                bc=settings,
                                doc=tempdoc)

            if isinstance(res, list):
                res[0].SetMg(c4d.Matrix())
                returnObject = res[0]

        if len(splineOutputs) == 1:
            returnObject = splineOutputs[0]

        genMat = op.GetMg()
        # transform the spline points into generator space. Otherwise cloner has issues cloning
        if returnObject is not None:
            
            matrix = returnObject.GetMg()

            if op[ID_PHONGTOSPLINE_INPUTLINK] is None:
                matrix = ~genMat * matrix

            pointCount = returnObject.GetPointCount()
            for pointIndex in range(0, pointCount):
                returnObject.SetPoint(pointIndex, matrix * returnObject.GetPoint(pointIndex))

        returnObject.SetMg(c4d.Matrix())

        if op[ID_PHONGTOSPLINE_OVERRIDETYPE]:
            TransferSplineMode(returnObject, op)

        return returnObject

    def GetDEnabling(self, node, id, t_data, flags, itemdesc):
        if id[0].id == ID_PHONGTOSPLINE_CLOSE:
            return node[ID_PHONGTOSPLINE_ISOPARMMODE] is 1
            
        if id[0].id == ID_PHONGTOSPLINE_SELECTION:
            return node[ID_PHONGTOSPLINE_ISOPARMMODE] is not 1

        if id[0].id == ID_PHONGTOSPLINE_SPLINETYPE or id[0].id == ID_PHONGTOSPLINE_SUBDIVISIONS:
            override = node[ID_PHONGTOSPLINE_OVERRIDETYPE]
            if override == 1:
                return True
            else:
                return False

        return True

    def CheckDirty(self, op, doc):
        inputLink = op[ID_PHONGTOSPLINE_INPUTLINK]

        usingInputLink = inputLink is not None
        if usingInputLink:
            firstChild = inputLink
        else:
            firstChild = op

        newDirty = CollectChildDirty(firstChild, op, not usingInputLink)
        if self.prevChildDirty != newDirty:
            self.prevChildDirty = newDirty
            op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def GetVirtualObjects(self, op, hh):
        inputLink = op[ID_PHONGTOSPLINE_INPUTLINK]
        edgeSelectionName = op[ID_PHONGTOSPLINE_SELECTION]

        useInputLink = inputLink is not None

        if inputLink is not None and inputLink.IsInstanceOf(c4d.Tbase):
            if inputLink.IsInstanceOf(c4d.Tedgeselection):
                edgeSelectionName = inputLink.GetName()
            inputLink = inputLink.GetObject()

        settingsDirty = False

        newDirty = 0
        if not useInputLink:
            newDirty = op.GetDirty(c4d.DIRTYFLAGS_DATA)
        else:
            newDirty = op.GetDirty(c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX)

        if newDirty != self.selfDirtyCount:
            self.selfDirtyCount = newDirty
            settingsDirty = True

        inputDirty = False

        op.NewDependenceList()

        if not useInputLink:    
            for child in op.GetChildren():
                op.GetHierarchyClone(hh, child, c4d.HIERARCHYCLONEFLAGS_ASPOLY, inputDirty, None, c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX)
        else:
            selfReferencing = CheckSelfReferencing(inputLink, op)
            if not selfReferencing:
                op.GetHierarchyClone(hh, inputLink, c4d.HIERARCHYCLONEFLAGS_ASPOLY, inputDirty, None, c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX)
                if not inputDirty:
                    inputLinkMatrixDirtyNew = inputLink.GetDirty(c4d.DIRTYFLAGS_MATRIX) + inputLink.GetHDirty(c4d.HDIRTYFLAGS_OBJECT_MATRIX)
                    if inputLinkMatrixDirtyNew != self.inputLinkMatrixDirty:
                        inputDirty = True
                        self.inputLinkMatrixDirty = inputLinkMatrixDirtyNew
        
        if not inputDirty:
            inputDirty = not op.CompareDependenceList()

        if not settingsDirty and not inputDirty:
            return op.GetCache(hh)

        firstChild = op.GetDown()

        if firstChild is None and inputLink is None: 
            return c4d.BaseObject(c4d.Onull);

        usingInputLink = inputLink is not None
        if usingInputLink:
            firstChild = inputLink
        else:
            firstChild = op

        returnObject = self.CreateSplineFromPolyEdges(firstChild, edgeSelectionName, op, not usingInputLink)

        if returnObject is not None:
            op.SetDirty(c4d.DIRTYFLAGS_DATA)
            self.selfDirtyCount =  self.selfDirtyCount + 1
            return returnObject

        # nothing was done. Output a dummy nullobj
        return c4d.BaseObject(c4d.Onull)

    def GetContour(self, op, doc, lod, bt):
        if op.GetDeformMode() == False:
            return None

        inputLink = op[ID_PHONGTOSPLINE_INPUTLINK]
        edgeSelectionName = op[ID_PHONGTOSPLINE_SELECTION]

        if inputLink is not None and inputLink.IsInstanceOf(c4d.Tbase):
            if inputLink.IsInstanceOf(c4d.Tedgeselection):
                edgeSelectionName = inputLink.GetName()
            inputLink = inputLink.GetObject()

        firstChild = op.GetDown()

        if firstChild is None and inputLink is None: 
            return None;

        usingInputLink = inputLink is not None
        if usingInputLink:
            firstChild = inputLink
        else:
            firstChild = op

        returnObject = self.CreateSplineFromPolyEdges(firstChild, edgeSelectionName, op, not usingInputLink)
        if returnObject is not None:
            returnObject.SetName(op.GetName())
        return returnObject

    def GetBubbleHelp(self, node):
        return "Convert Phong breaks to Spline Objects"


if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(id=ID_PHONGTOSPLINE,
                                     str="Phong To Spline",
                                     g=PhongToSplineObjectData,
                                     description="opyphongtosplineobject",
                                     icon=c4d.bitmaps.InitResourceBitmap(1019730),
                                     info=c4d.OBJECT_GENERATOR | c4d.OBJECT_ISSPLINE)

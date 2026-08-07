-- CreateTable
CREATE TABLE "Organization" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "industry" TEXT,
    "website" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "businessType" TEXT,
    "typicalTolerance" REAL,
    "typicalQuantity" TEXT,
    "outsourced" TEXT,
    "bottlenecks" TEXT,
    "onboardingDone" BOOLEAN NOT NULL DEFAULT false,
    "defaultSharing" TEXT NOT NULL DEFAULT 'PRIVATE'
);

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "email" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'ENGINEER',
    "organizationId" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lastSeenAt" DATETIME,
    CONSTRAINT "User_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Session" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "token" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "expiresAt" DATETIME NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "userAgent" TEXT,
    CONSTRAINT "Session_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Shop" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "location" TEXT,
    "shiftHours" REAL NOT NULL DEFAULT 8,
    "machineRate" REAL NOT NULL DEFAULT 75,
    "operatorRate" REAL NOT NULL DEFAULT 38,
    "inspectionRate" REAL NOT NULL DEFAULT 45,
    "overheadRate" REAL NOT NULL DEFAULT 0.18,
    "marginRate" REAL NOT NULL DEFAULT 0.32,
    CONSTRAINT "Shop_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Machine" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "manufacturer" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "controller" TEXT NOT NULL,
    "machineType" TEXT NOT NULL,
    "axisCount" INTEGER NOT NULL DEFAULT 3,
    "travelsX" REAL NOT NULL,
    "travelsY" REAL NOT NULL,
    "travelsZ" REAL NOT NULL,
    "tableX" REAL NOT NULL,
    "tableY" REAL NOT NULL,
    "maxSpindleRPM" INTEGER NOT NULL,
    "maxSpindlePower" REAL NOT NULL,
    "maxSpindleTorque" REAL NOT NULL,
    "maxFeed" REAL NOT NULL,
    "maxRapid" REAL NOT NULL,
    "toolChangerCapacity" INTEGER NOT NULL,
    "maxToolDiameter" REAL NOT NULL,
    "maxToolLength" REAL NOT NULL,
    "maxToolWeight" REAL NOT NULL,
    "coolantTypes" TEXT NOT NULL,
    "throughSpindleCoolant" BOOLEAN NOT NULL DEFAULT false,
    "probe" BOOLEAN NOT NULL DEFAULT false,
    "toolSetter" BOOLEAN NOT NULL DEFAULT false,
    "fourthAxis" BOOLEAN NOT NULL DEFAULT false,
    "fifthAxis" BOOLEAN NOT NULL DEFAULT false,
    "supportedPostProcessor" TEXT NOT NULL,
    "isReferenceProfile" BOOLEAN NOT NULL DEFAULT false,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Machine_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Tool" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "toolNumber" INTEGER NOT NULL,
    "toolClass" TEXT NOT NULL,
    "manufacturer" TEXT,
    "product" TEXT,
    "description" TEXT NOT NULL,
    "diameter" REAL NOT NULL,
    "cornerRadius" REAL NOT NULL DEFAULT 0,
    "flutes" INTEGER NOT NULL,
    "material" TEXT NOT NULL,
    "coating" TEXT,
    "fluteLength" REAL NOT NULL,
    "overallLength" REAL NOT NULL,
    "stickout" REAL NOT NULL,
    "holderId" TEXT,
    "maxRPM" INTEGER NOT NULL,
    "recommendedMaterials" TEXT NOT NULL,
    "chiploadMin" REAL NOT NULL,
    "chiploadMax" REAL NOT NULL,
    "sfmMin" REAL NOT NULL,
    "sfmMax" REAL NOT NULL,
    "coolant" TEXT NOT NULL,
    "lifeRemaining" REAL NOT NULL DEFAULT 1,
    "costPerTool" REAL NOT NULL DEFAULT 0,
    "expectedLifeMinutes" REAL NOT NULL DEFAULT 120,
    "notes" TEXT,
    CONSTRAINT "Tool_holderId_fkey" FOREIGN KEY ("holderId") REFERENCES "ToolHolder" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Tool_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ToolHolder" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "description" TEXT NOT NULL,
    "taper" TEXT NOT NULL,
    "noseDiameter" REAL NOT NULL,
    "gaugeLength" REAL NOT NULL,
    "taperAngleDegrees" REAL NOT NULL DEFAULT 0
);

-- CreateTable
CREATE TABLE "WorkholdingDevice" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "manufacturer" TEXT,
    "model" TEXT,
    "description" TEXT NOT NULL,
    "jawWidth" REAL NOT NULL,
    "jawHeight" REAL NOT NULL,
    "maxOpening" REAL NOT NULL,
    "clampForce" REAL,
    "fixtureHeight" REAL NOT NULL,
    "mountingGeometry" TEXT,
    "hasCadRepresentation" BOOLEAN NOT NULL DEFAULT false,
    "notes" TEXT,
    CONSTRAINT "WorkholdingDevice_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "JawBlank" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "material" TEXT NOT NULL,
    "width" REAL NOT NULL,
    "height" REAL NOT NULL,
    "thickness" REAL NOT NULL,
    "boltPattern" TEXT NOT NULL,
    "quantityOnHand" INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT "JawBlank_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Jaw" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "setupId" TEXT,
    "deviceId" TEXT,
    "blankId" TEXT,
    "side" TEXT NOT NULL,
    "stepDepth" REAL NOT NULL,
    "stepHeight" REAL NOT NULL,
    "seatWidth" REAL NOT NULL,
    "seatDepth" REAL NOT NULL,
    "seatCornerRadius" REAL NOT NULL,
    "stopLocation" REAL,
    "reliefRadius" REAL NOT NULL,
    "clampingDirection" TEXT NOT NULL DEFAULT 'X',
    "processJson" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Jaw_setupId_fkey" FOREIGN KEY ("setupId") REFERENCES "Setup" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Jaw_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "WorkholdingDevice" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Jaw_blankId_fkey" FOREIGN KEY ("blankId") REFERENCES "JawBlank" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Material" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "family" TEXT NOT NULL,
    "condition" TEXT NOT NULL,
    "density" REAL NOT NULL,
    "hardness" REAL,
    "yieldStrength" REAL,
    "tensileStrength" REAL,
    "machinabilityRating" REAL NOT NULL,
    "sfmCarbideMin" REAL NOT NULL,
    "sfmCarbideMax" REAL NOT NULL,
    "specificEnergy" REAL NOT NULL DEFAULT 0.3,
    "costPerPound" REAL NOT NULL,
    "weldable" BOOLEAN NOT NULL DEFAULT true,
    "castable" BOOLEAN NOT NULL DEFAULT false,
    "notes" TEXT,
    CONSTRAINT "Material_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "MetrologyDevice" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "deviceType" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "rangeMin" REAL,
    "rangeMax" REAL,
    "resolution" REAL NOT NULL,
    "uncertainty" REAL NOT NULL,
    "calibrated" BOOLEAN NOT NULL DEFAULT false,
    "calibrationDue" DATETIME,
    CONSTRAINT "MetrologyDevice_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Part" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "partNumber" TEXT,
    "description" TEXT,
    "sharing" TEXT NOT NULL DEFAULT 'PRIVATE',
    "isDemo" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Part_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PartRevision" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partId" TEXT NOT NULL,
    "revision" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'DRAFT',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "intentJson" TEXT NOT NULL,
    "units" TEXT NOT NULL DEFAULT 'IN',
    "stockJson" TEXT,
    "notes" TEXT,
    CONSTRAINT "PartRevision_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Feature" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "functionalRole" TEXT NOT NULL DEFAULT 'NONE',
    "critical" BOOLEAN NOT NULL DEFAULT false,
    "parametersJson" TEXT NOT NULL,
    "tolerancePlus" REAL,
    "toleranceMinus" REAL,
    "surfaceFinish" REAL,
    "inspectionMethod" TEXT,
    "notes" TEXT,
    "orderIndex" INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT "Feature_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PartResponsibilityProfile" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "loadBearing" BOOLEAN,
    "safetyCritical" BOOLEAN,
    "failureConsequence" TEXT,
    "loadingTypes" TEXT NOT NULL DEFAULT '[]',
    "environments" TEXT NOT NULL DEFAULT '[]',
    "temperatureMin" REAL,
    "temperatureMax" REAL,
    "serviceLifeYears" REAL,
    "productionIntent" TEXT,
    "annualVolume" INTEGER,
    "regulatory" TEXT NOT NULL DEFAULT '[]',
    "materialCertRequired" BOOLEAN,
    "traceabilityRequired" BOOLEAN,
    "inspectionRequirements" TEXT NOT NULL DEFAULT '[]',
    "answeredBy" TEXT,
    "answeredAt" DATETIME,
    CONSTRAINT "PartResponsibilityProfile_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Drawing" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "assetId" TEXT,
    "title" TEXT NOT NULL,
    "sheetNumber" TEXT,
    "extractedText" TEXT,
    "processingState" TEXT NOT NULL DEFAULT 'PENDING',
    CONSTRAINT "Drawing_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Drawing_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "UploadedAsset" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "UploadedAsset" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT,
    "revision" TEXT,
    "kind" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "mimeType" TEXT NOT NULL,
    "size" INTEGER NOT NULL,
    "checksum" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "uploadedBy" TEXT NOT NULL,
    "privacy" TEXT NOT NULL DEFAULT 'PRIVATE',
    "processingState" TEXT NOT NULL DEFAULT 'STORED',
    "extractedMetadata" TEXT,
    "viewLabel" TEXT,
    "scaleReference" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "UploadedAsset_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "UploadedAsset_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "MeasurementSession" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "mode" TEXT NOT NULL DEFAULT 'REVERSE_ENGINEER',
    "status" TEXT NOT NULL DEFAULT 'IN_PROGRESS',
    "operator" TEXT,
    "temperatureF" REAL,
    "startedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" DATETIME,
    "notes" TEXT,
    CONSTRAINT "MeasurementSession_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Measurement" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sessionId" TEXT NOT NULL,
    "featureId" TEXT,
    "assetId" TEXT,
    "deviceId" TEXT,
    "label" TEXT NOT NULL,
    "measuredValue" REAL NOT NULL,
    "units" TEXT NOT NULL DEFAULT 'IN',
    "uncertainty" REAL NOT NULL,
    "repeatCount" INTEGER NOT NULL DEFAULT 1,
    "context" TEXT NOT NULL DEFAULT 'GENERAL',
    "suggestedNominal" REAL,
    "suggestedNominalLabel" TEXT,
    "suggestedFamily" TEXT,
    "suggestionConfidence" REAL,
    "suggestionBasis" TEXT,
    "resolution" TEXT NOT NULL DEFAULT 'PENDING',
    "resolvedValue" REAL,
    "resolvedBy" TEXT,
    "resolvedAt" DATETIME,
    "dependsOn" TEXT NOT NULL DEFAULT '[]',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Measurement_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "MeasurementSession" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Measurement_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Measurement_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "UploadedAsset" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Measurement_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "MetrologyDevice" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Setup" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "sequence" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "orientation" TEXT NOT NULL DEFAULT 'TOP',
    "machineId" TEXT,
    "workholdingId" TEXT,
    "workOffset" TEXT NOT NULL DEFAULT 'G54',
    "datumNote" TEXT,
    "gripDepth" REAL,
    "gripLength" REAL,
    "stockProjection" REAL,
    "parallelHeight" REAL,
    "riskLevel" TEXT,
    "riskFactorsJson" TEXT,
    "estimatedCycleMinutes" REAL,
    "notes" TEXT,
    CONSTRAINT "Setup_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Setup_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Setup_workholdingId_fkey" FOREIGN KEY ("workholdingId") REFERENCES "WorkholdingDevice" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Operation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "setupId" TEXT NOT NULL,
    "featureId" TEXT,
    "toolId" TEXT,
    "sequence" INTEGER NOT NULL,
    "type" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "topZ" REAL NOT NULL,
    "finalZ" REAL NOT NULL,
    "clearanceZ" REAL NOT NULL DEFAULT 0.25,
    "retractZ" REAL NOT NULL DEFAULT 1,
    "overridesJson" TEXT,
    "parametersJson" TEXT,
    "cycleTimeMinutes" REAL,
    "materialRemoved" REAL,
    "cuttingDistance" REAL,
    "warningsJson" TEXT,
    "isPlaceholder" BOOLEAN NOT NULL DEFAULT false,
    "errorReason" TEXT,
    CONSTRAINT "Operation_setupId_fkey" FOREIGN KEY ("setupId") REFERENCES "Setup" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Operation_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Operation_toolId_fkey" FOREIGN KEY ("toolId") REFERENCES "Tool" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Toolpath" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "operationId" TEXT NOT NULL,
    "movesJson" TEXT NOT NULL,
    "moveCount" INTEGER NOT NULL,
    "generatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "engineVersion" TEXT NOT NULL DEFAULT 'phase1-prototype',
    CONSTRAINT "Toolpath_operationId_fkey" FOREIGN KEY ("operationId") REFERENCES "Operation" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Simulation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "setupId" TEXT NOT NULL,
    "kind" TEXT NOT NULL DEFAULT 'VISUALIZATION',
    "status" TEXT NOT NULL DEFAULT 'COMPLETE',
    "verifiedStockRemoval" BOOLEAN NOT NULL DEFAULT false,
    "collisionChecked" BOOLEAN NOT NULL DEFAULT false,
    "resultJson" TEXT,
    "runAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Simulation_setupId_fkey" FOREIGN KEY ("setupId") REFERENCES "Setup" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "NCProgram" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "machineId" TEXT,
    "postId" TEXT NOT NULL,
    "programNumber" TEXT NOT NULL,
    "workOffset" TEXT NOT NULL DEFAULT 'G54',
    "units" TEXT NOT NULL DEFAULT 'IN',
    "code" TEXT NOT NULL,
    "certified" BOOLEAN NOT NULL DEFAULT false,
    "verificationIssuesJson" TEXT,
    "preflightJson" TEXT,
    "generatedBy" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "NCProgram_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "NCProgram_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PostProcessor" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "controllerFamily" TEXT NOT NULL,
    "certified" BOOLEAN NOT NULL DEFAULT false,
    "notes" TEXT
);

-- CreateTable
CREATE TABLE "InspectionPlan" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "samplingPlan" TEXT NOT NULL DEFAULT 'FIRST_ARTICLE',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "InspectionPlan_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "InspectionItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "planId" TEXT NOT NULL,
    "featureId" TEXT,
    "label" TEXT NOT NULL,
    "nominal" REAL NOT NULL,
    "plusTol" REAL NOT NULL,
    "minusTol" REAL NOT NULL,
    "method" TEXT NOT NULL,
    "deviceType" TEXT,
    "sequence" INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT "InspectionItem_planId_fkey" FOREIGN KEY ("planId") REFERENCES "InspectionPlan" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "InspectionItem_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "InspectionResult" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "planId" TEXT NOT NULL,
    "itemId" TEXT NOT NULL,
    "jobId" TEXT,
    "measured" REAL NOT NULL,
    "pass" BOOLEAN NOT NULL,
    "inspector" TEXT,
    "measuredAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "notes" TEXT,
    CONSTRAINT "InspectionResult_planId_fkey" FOREIGN KEY ("planId") REFERENCES "InspectionPlan" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "InspectionResult_itemId_fkey" FOREIGN KEY ("itemId") REFERENCES "InspectionItem" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "InspectionResult_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Job" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT NOT NULL,
    "revision" TEXT NOT NULL,
    "jobNumber" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PLANNED',
    "dueDate" DATETIME,
    "startedAt" DATETIME,
    "completedAt" DATETIME,
    "actualCycleMinutes" REAL,
    "actualSetupHours" REAL,
    "scrapCount" INTEGER NOT NULL DEFAULT 0,
    "notes" TEXT,
    CONSTRAINT "Job_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Job_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "JobOutcome" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "jobId" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "operationId" TEXT,
    "toolNumber" INTEGER,
    "cause" TEXT NOT NULL,
    "correctiveAction" TEXT NOT NULL,
    "partsAffected" INTEGER NOT NULL DEFAULT 0,
    "notes" TEXT,
    "recordedBy" TEXT,
    "recordedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "JobOutcome_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ManufacturingDNA" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partId" TEXT NOT NULL,
    "revision" TEXT NOT NULL,
    "jobId" TEXT,
    "snapshotJson" TEXT NOT NULL,
    "actualResultsJson" TEXT,
    "costActual" REAL,
    "supplierId" TEXT,
    "recordedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ManufacturingDNA_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "ManufacturingDNA_supplierId_fkey" FOREIGN KEY ("supplierId") REFERENCES "Supplier" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Quote" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT NOT NULL,
    "quoteNumber" TEXT NOT NULL,
    "customer" TEXT,
    "status" TEXT NOT NULL DEFAULT 'DRAFT',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "validUntil" DATETIME,
    CONSTRAINT "Quote_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Quote_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "CostEstimate" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "quoteId" TEXT,
    "quantity" INTEGER NOT NULL,
    "assumptionsJson" TEXT NOT NULL,
    "linesJson" TEXT NOT NULL,
    "unitCost" REAL NOT NULL,
    "unitPrice" REAL NOT NULL,
    "lotPrice" REAL NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdBy" TEXT,
    CONSTRAINT "CostEstimate_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "CostEstimate_quoteId_fkey" FOREIGN KEY ("quoteId") REFERENCES "Quote" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Supplier" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "capabilities" TEXT NOT NULL DEFAULT '[]',
    "certifications" TEXT NOT NULL DEFAULT '[]',
    "leadTimeDays" INTEGER,
    "notes" TEXT,
    CONSTRAINT "Supplier_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "NetworkFingerprint" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT NOT NULL,
    "fingerprintJson" TEXT NOT NULL,
    "published" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "NetworkFingerprint_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "NetworkFingerprint_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "NetworkPermission" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "scope" TEXT NOT NULL,
    "targetId" TEXT,
    "level" TEXT NOT NULL DEFAULT 'PRIVATE',
    "grantedBy" TEXT NOT NULL,
    "grantedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revokedAt" DATETIME,
    CONSTRAINT "NetworkPermission_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Conversation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT,
    "title" TEXT NOT NULL DEFAULT 'Copilot',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Conversation_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Conversation_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ConversationMessage" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "conversationId" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "referencesJson" TEXT,
    "needsJson" TEXT,
    "providerId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ConversationMessage_conversationId_fkey" FOREIGN KEY ("conversationId") REFERENCES "Conversation" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "AIRecommendation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "summary" TEXT NOT NULL,
    "payloadJson" TEXT NOT NULL,
    "providerId" TEXT NOT NULL,
    "confidence" REAL,
    "status" TEXT NOT NULL DEFAULT 'PROPOSED',
    "decidedBy" TEXT,
    "decidedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "AIRecommendation_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Approval" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "scope" TEXT NOT NULL,
    "approvedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "statement" TEXT NOT NULL,
    "revokedAt" DATETIME,
    CONSTRAINT "Approval_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Approval_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "AuditLog" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "userId" TEXT,
    "entityType" TEXT NOT NULL,
    "entityId" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "field" TEXT,
    "oldValue" TEXT,
    "newValue" TEXT,
    "actorType" TEXT NOT NULL DEFAULT 'HUMAN',
    "reason" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "AuditLog_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "AuditLog_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Organization_slug_key" ON "Organization"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "User_organizationId_idx" ON "User"("organizationId");

-- CreateIndex
CREATE UNIQUE INDEX "Session_token_key" ON "Session"("token");

-- CreateIndex
CREATE INDEX "Session_userId_idx" ON "Session"("userId");

-- CreateIndex
CREATE INDEX "Shop_organizationId_idx" ON "Shop"("organizationId");

-- CreateIndex
CREATE INDEX "Machine_organizationId_idx" ON "Machine"("organizationId");

-- CreateIndex
CREATE INDEX "Tool_organizationId_idx" ON "Tool"("organizationId");

-- CreateIndex
CREATE UNIQUE INDEX "Tool_organizationId_toolNumber_key" ON "Tool"("organizationId", "toolNumber");

-- CreateIndex
CREATE INDEX "WorkholdingDevice_organizationId_idx" ON "WorkholdingDevice"("organizationId");

-- CreateIndex
CREATE INDEX "JawBlank_organizationId_idx" ON "JawBlank"("organizationId");

-- CreateIndex
CREATE INDEX "Jaw_setupId_idx" ON "Jaw"("setupId");

-- CreateIndex
CREATE INDEX "Material_organizationId_idx" ON "Material"("organizationId");

-- CreateIndex
CREATE INDEX "MetrologyDevice_organizationId_idx" ON "MetrologyDevice"("organizationId");

-- CreateIndex
CREATE INDEX "Part_organizationId_idx" ON "Part"("organizationId");

-- CreateIndex
CREATE INDEX "PartRevision_partId_idx" ON "PartRevision"("partId");

-- CreateIndex
CREATE UNIQUE INDEX "PartRevision_partId_revision_key" ON "PartRevision"("partId", "revision");

-- CreateIndex
CREATE INDEX "Feature_partRevisionId_idx" ON "Feature"("partRevisionId");

-- CreateIndex
CREATE UNIQUE INDEX "PartResponsibilityProfile_partRevisionId_key" ON "PartResponsibilityProfile"("partRevisionId");

-- CreateIndex
CREATE INDEX "Drawing_partRevisionId_idx" ON "Drawing"("partRevisionId");

-- CreateIndex
CREATE INDEX "UploadedAsset_organizationId_idx" ON "UploadedAsset"("organizationId");

-- CreateIndex
CREATE INDEX "UploadedAsset_partId_idx" ON "UploadedAsset"("partId");

-- CreateIndex
CREATE INDEX "MeasurementSession_partRevisionId_idx" ON "MeasurementSession"("partRevisionId");

-- CreateIndex
CREATE INDEX "Measurement_sessionId_idx" ON "Measurement"("sessionId");

-- CreateIndex
CREATE INDEX "Setup_partRevisionId_idx" ON "Setup"("partRevisionId");

-- CreateIndex
CREATE UNIQUE INDEX "Setup_partRevisionId_sequence_key" ON "Setup"("partRevisionId", "sequence");

-- CreateIndex
CREATE INDEX "Operation_setupId_idx" ON "Operation"("setupId");

-- CreateIndex
CREATE UNIQUE INDEX "Toolpath_operationId_key" ON "Toolpath"("operationId");

-- CreateIndex
CREATE INDEX "Simulation_setupId_idx" ON "Simulation"("setupId");

-- CreateIndex
CREATE INDEX "NCProgram_partRevisionId_idx" ON "NCProgram"("partRevisionId");

-- CreateIndex
CREATE INDEX "InspectionPlan_partRevisionId_idx" ON "InspectionPlan"("partRevisionId");

-- CreateIndex
CREATE INDEX "InspectionItem_planId_idx" ON "InspectionItem"("planId");

-- CreateIndex
CREATE INDEX "InspectionResult_planId_idx" ON "InspectionResult"("planId");

-- CreateIndex
CREATE INDEX "Job_organizationId_idx" ON "Job"("organizationId");

-- CreateIndex
CREATE INDEX "Job_partId_idx" ON "Job"("partId");

-- CreateIndex
CREATE INDEX "JobOutcome_jobId_idx" ON "JobOutcome"("jobId");

-- CreateIndex
CREATE INDEX "ManufacturingDNA_partId_idx" ON "ManufacturingDNA"("partId");

-- CreateIndex
CREATE INDEX "Quote_organizationId_idx" ON "Quote"("organizationId");

-- CreateIndex
CREATE INDEX "CostEstimate_partRevisionId_idx" ON "CostEstimate"("partRevisionId");

-- CreateIndex
CREATE INDEX "Supplier_organizationId_idx" ON "Supplier"("organizationId");

-- CreateIndex
CREATE INDEX "NetworkFingerprint_organizationId_idx" ON "NetworkFingerprint"("organizationId");

-- CreateIndex
CREATE INDEX "NetworkPermission_organizationId_idx" ON "NetworkPermission"("organizationId");

-- CreateIndex
CREATE INDEX "Conversation_organizationId_idx" ON "Conversation"("organizationId");

-- CreateIndex
CREATE INDEX "ConversationMessage_conversationId_idx" ON "ConversationMessage"("conversationId");

-- CreateIndex
CREATE INDEX "AIRecommendation_partRevisionId_idx" ON "AIRecommendation"("partRevisionId");

-- CreateIndex
CREATE INDEX "Approval_partRevisionId_idx" ON "Approval"("partRevisionId");

-- CreateIndex
CREATE INDEX "AuditLog_organizationId_idx" ON "AuditLog"("organizationId");

-- CreateIndex
CREATE INDEX "AuditLog_entityType_entityId_idx" ON "AuditLog"("entityType", "entityId");

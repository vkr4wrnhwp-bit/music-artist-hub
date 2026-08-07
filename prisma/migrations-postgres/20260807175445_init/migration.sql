-- CreateTable
CREATE TABLE "Organization" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "industry" TEXT,
    "website" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "businessType" TEXT,
    "typicalTolerance" DOUBLE PRECISION,
    "typicalQuantity" TEXT,
    "outsourced" TEXT,
    "bottlenecks" TEXT,
    "onboardingDone" BOOLEAN NOT NULL DEFAULT false,
    "defaultSharing" TEXT NOT NULL DEFAULT 'PRIVATE',

    CONSTRAINT "Organization_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'ENGINEER',
    "organizationId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lastSeenAt" TIMESTAMP(3),

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Session" (
    "id" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "userAgent" TEXT,

    CONSTRAINT "Session_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Shop" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "location" TEXT,
    "shiftHours" DOUBLE PRECISION NOT NULL DEFAULT 8,
    "machineRate" DOUBLE PRECISION NOT NULL DEFAULT 75,
    "operatorRate" DOUBLE PRECISION NOT NULL DEFAULT 38,
    "inspectionRate" DOUBLE PRECISION NOT NULL DEFAULT 45,
    "overheadRate" DOUBLE PRECISION NOT NULL DEFAULT 0.18,
    "marginRate" DOUBLE PRECISION NOT NULL DEFAULT 0.32,

    CONSTRAINT "Shop_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Machine" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "manufacturer" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "controller" TEXT NOT NULL,
    "machineType" TEXT NOT NULL,
    "axisCount" INTEGER NOT NULL DEFAULT 3,
    "travelsX" DOUBLE PRECISION NOT NULL,
    "travelsY" DOUBLE PRECISION NOT NULL,
    "travelsZ" DOUBLE PRECISION NOT NULL,
    "tableX" DOUBLE PRECISION NOT NULL,
    "tableY" DOUBLE PRECISION NOT NULL,
    "maxSpindleRPM" INTEGER NOT NULL,
    "maxSpindlePower" DOUBLE PRECISION NOT NULL,
    "maxSpindleTorque" DOUBLE PRECISION NOT NULL,
    "maxFeed" DOUBLE PRECISION NOT NULL,
    "maxRapid" DOUBLE PRECISION NOT NULL,
    "toolChangerCapacity" INTEGER NOT NULL,
    "maxToolDiameter" DOUBLE PRECISION NOT NULL,
    "maxToolLength" DOUBLE PRECISION NOT NULL,
    "maxToolWeight" DOUBLE PRECISION NOT NULL,
    "coolantTypes" TEXT NOT NULL,
    "throughSpindleCoolant" BOOLEAN NOT NULL DEFAULT false,
    "probe" BOOLEAN NOT NULL DEFAULT false,
    "toolSetter" BOOLEAN NOT NULL DEFAULT false,
    "fourthAxis" BOOLEAN NOT NULL DEFAULT false,
    "fifthAxis" BOOLEAN NOT NULL DEFAULT false,
    "supportedPostProcessor" TEXT NOT NULL,
    "isReferenceProfile" BOOLEAN NOT NULL DEFAULT false,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Machine_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Tool" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "toolNumber" INTEGER NOT NULL,
    "toolClass" TEXT NOT NULL,
    "manufacturer" TEXT,
    "product" TEXT,
    "description" TEXT NOT NULL,
    "diameter" DOUBLE PRECISION NOT NULL,
    "cornerRadius" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "flutes" INTEGER NOT NULL,
    "material" TEXT NOT NULL,
    "coating" TEXT,
    "fluteLength" DOUBLE PRECISION NOT NULL,
    "overallLength" DOUBLE PRECISION NOT NULL,
    "stickout" DOUBLE PRECISION NOT NULL,
    "holderId" TEXT,
    "maxRPM" INTEGER NOT NULL,
    "recommendedMaterials" TEXT NOT NULL,
    "chiploadMin" DOUBLE PRECISION NOT NULL,
    "chiploadMax" DOUBLE PRECISION NOT NULL,
    "sfmMin" DOUBLE PRECISION NOT NULL,
    "sfmMax" DOUBLE PRECISION NOT NULL,
    "coolant" TEXT NOT NULL,
    "lifeRemaining" DOUBLE PRECISION NOT NULL DEFAULT 1,
    "costPerTool" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "expectedLifeMinutes" DOUBLE PRECISION NOT NULL DEFAULT 120,
    "notes" TEXT,

    CONSTRAINT "Tool_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ToolHolder" (
    "id" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "taper" TEXT NOT NULL,
    "noseDiameter" DOUBLE PRECISION NOT NULL,
    "gaugeLength" DOUBLE PRECISION NOT NULL,
    "taperAngleDegrees" DOUBLE PRECISION NOT NULL DEFAULT 0,

    CONSTRAINT "ToolHolder_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "WorkholdingDevice" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "manufacturer" TEXT,
    "model" TEXT,
    "description" TEXT NOT NULL,
    "jawWidth" DOUBLE PRECISION NOT NULL,
    "jawHeight" DOUBLE PRECISION NOT NULL,
    "maxOpening" DOUBLE PRECISION NOT NULL,
    "clampForce" DOUBLE PRECISION,
    "fixtureHeight" DOUBLE PRECISION NOT NULL,
    "mountingGeometry" TEXT,
    "hasCadRepresentation" BOOLEAN NOT NULL DEFAULT false,
    "notes" TEXT,

    CONSTRAINT "WorkholdingDevice_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "JawBlank" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "material" TEXT NOT NULL,
    "width" DOUBLE PRECISION NOT NULL,
    "height" DOUBLE PRECISION NOT NULL,
    "thickness" DOUBLE PRECISION NOT NULL,
    "boltPattern" TEXT NOT NULL,
    "quantityOnHand" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "JawBlank_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Jaw" (
    "id" TEXT NOT NULL,
    "setupId" TEXT,
    "deviceId" TEXT,
    "blankId" TEXT,
    "side" TEXT NOT NULL,
    "stepDepth" DOUBLE PRECISION NOT NULL,
    "stepHeight" DOUBLE PRECISION NOT NULL,
    "seatWidth" DOUBLE PRECISION NOT NULL,
    "seatDepth" DOUBLE PRECISION NOT NULL,
    "seatCornerRadius" DOUBLE PRECISION NOT NULL,
    "stopLocation" DOUBLE PRECISION,
    "reliefRadius" DOUBLE PRECISION NOT NULL,
    "clampingDirection" TEXT NOT NULL DEFAULT 'X',
    "processJson" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Jaw_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Material" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "family" TEXT NOT NULL,
    "condition" TEXT NOT NULL,
    "density" DOUBLE PRECISION NOT NULL,
    "hardness" DOUBLE PRECISION,
    "yieldStrength" DOUBLE PRECISION,
    "tensileStrength" DOUBLE PRECISION,
    "machinabilityRating" DOUBLE PRECISION NOT NULL,
    "sfmCarbideMin" DOUBLE PRECISION NOT NULL,
    "sfmCarbideMax" DOUBLE PRECISION NOT NULL,
    "specificEnergy" DOUBLE PRECISION NOT NULL DEFAULT 0.3,
    "costPerPound" DOUBLE PRECISION NOT NULL,
    "weldable" BOOLEAN NOT NULL DEFAULT true,
    "castable" BOOLEAN NOT NULL DEFAULT false,
    "notes" TEXT,

    CONSTRAINT "Material_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "MetrologyDevice" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "deviceType" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "rangeMin" DOUBLE PRECISION,
    "rangeMax" DOUBLE PRECISION,
    "resolution" DOUBLE PRECISION NOT NULL,
    "uncertainty" DOUBLE PRECISION NOT NULL,
    "calibrated" BOOLEAN NOT NULL DEFAULT false,
    "calibrationDue" TIMESTAMP(3),

    CONSTRAINT "MetrologyDevice_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Part" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "partNumber" TEXT,
    "description" TEXT,
    "sharing" TEXT NOT NULL DEFAULT 'PRIVATE',
    "isDemo" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Part_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PartRevision" (
    "id" TEXT NOT NULL,
    "partId" TEXT NOT NULL,
    "revision" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'DRAFT',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "intentJson" TEXT NOT NULL,
    "units" TEXT NOT NULL DEFAULT 'IN',
    "stockJson" TEXT,
    "notes" TEXT,

    CONSTRAINT "PartRevision_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Feature" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "functionalRole" TEXT NOT NULL DEFAULT 'NONE',
    "critical" BOOLEAN NOT NULL DEFAULT false,
    "parametersJson" TEXT NOT NULL,
    "tolerancePlus" DOUBLE PRECISION,
    "toleranceMinus" DOUBLE PRECISION,
    "surfaceFinish" DOUBLE PRECISION,
    "inspectionMethod" TEXT,
    "notes" TEXT,
    "orderIndex" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "Feature_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PartResponsibilityProfile" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "loadBearing" BOOLEAN,
    "safetyCritical" BOOLEAN,
    "failureConsequence" TEXT,
    "loadingTypes" TEXT NOT NULL DEFAULT '[]',
    "environments" TEXT NOT NULL DEFAULT '[]',
    "temperatureMin" DOUBLE PRECISION,
    "temperatureMax" DOUBLE PRECISION,
    "serviceLifeYears" DOUBLE PRECISION,
    "productionIntent" TEXT,
    "annualVolume" INTEGER,
    "regulatory" TEXT NOT NULL DEFAULT '[]',
    "materialCertRequired" BOOLEAN,
    "traceabilityRequired" BOOLEAN,
    "inspectionRequirements" TEXT NOT NULL DEFAULT '[]',
    "answeredBy" TEXT,
    "answeredAt" TIMESTAMP(3),

    CONSTRAINT "PartResponsibilityProfile_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Drawing" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "assetId" TEXT,
    "title" TEXT NOT NULL,
    "sheetNumber" TEXT,
    "extractedText" TEXT,
    "processingState" TEXT NOT NULL DEFAULT 'PENDING',

    CONSTRAINT "Drawing_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UploadedAsset" (
    "id" TEXT NOT NULL,
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
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "UploadedAsset_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "MeasurementSession" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "mode" TEXT NOT NULL DEFAULT 'REVERSE_ENGINEER',
    "status" TEXT NOT NULL DEFAULT 'IN_PROGRESS',
    "operator" TEXT,
    "temperatureF" DOUBLE PRECISION,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),
    "notes" TEXT,

    CONSTRAINT "MeasurementSession_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Measurement" (
    "id" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "featureId" TEXT,
    "assetId" TEXT,
    "deviceId" TEXT,
    "label" TEXT NOT NULL,
    "measuredValue" DOUBLE PRECISION NOT NULL,
    "units" TEXT NOT NULL DEFAULT 'IN',
    "uncertainty" DOUBLE PRECISION NOT NULL,
    "repeatCount" INTEGER NOT NULL DEFAULT 1,
    "context" TEXT NOT NULL DEFAULT 'GENERAL',
    "suggestedNominal" DOUBLE PRECISION,
    "suggestedNominalLabel" TEXT,
    "suggestedFamily" TEXT,
    "suggestionConfidence" DOUBLE PRECISION,
    "suggestionBasis" TEXT,
    "resolution" TEXT NOT NULL DEFAULT 'PENDING',
    "resolvedValue" DOUBLE PRECISION,
    "resolvedBy" TEXT,
    "resolvedAt" TIMESTAMP(3),
    "dependsOn" TEXT NOT NULL DEFAULT '[]',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Measurement_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Setup" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "sequence" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "orientation" TEXT NOT NULL DEFAULT 'TOP',
    "machineId" TEXT,
    "workholdingId" TEXT,
    "workOffset" TEXT NOT NULL DEFAULT 'G54',
    "datumNote" TEXT,
    "gripDepth" DOUBLE PRECISION,
    "gripLength" DOUBLE PRECISION,
    "stockProjection" DOUBLE PRECISION,
    "parallelHeight" DOUBLE PRECISION,
    "riskLevel" TEXT,
    "riskFactorsJson" TEXT,
    "estimatedCycleMinutes" DOUBLE PRECISION,
    "notes" TEXT,

    CONSTRAINT "Setup_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Operation" (
    "id" TEXT NOT NULL,
    "setupId" TEXT NOT NULL,
    "featureId" TEXT,
    "toolId" TEXT,
    "sequence" INTEGER NOT NULL,
    "type" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "topZ" DOUBLE PRECISION NOT NULL,
    "finalZ" DOUBLE PRECISION NOT NULL,
    "clearanceZ" DOUBLE PRECISION NOT NULL DEFAULT 0.25,
    "retractZ" DOUBLE PRECISION NOT NULL DEFAULT 1,
    "overridesJson" TEXT,
    "parametersJson" TEXT,
    "cycleTimeMinutes" DOUBLE PRECISION,
    "materialRemoved" DOUBLE PRECISION,
    "cuttingDistance" DOUBLE PRECISION,
    "warningsJson" TEXT,
    "isPlaceholder" BOOLEAN NOT NULL DEFAULT false,
    "errorReason" TEXT,

    CONSTRAINT "Operation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Toolpath" (
    "id" TEXT NOT NULL,
    "operationId" TEXT NOT NULL,
    "movesJson" TEXT NOT NULL,
    "moveCount" INTEGER NOT NULL,
    "generatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "engineVersion" TEXT NOT NULL DEFAULT 'phase1-prototype',

    CONSTRAINT "Toolpath_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Simulation" (
    "id" TEXT NOT NULL,
    "setupId" TEXT NOT NULL,
    "kind" TEXT NOT NULL DEFAULT 'VISUALIZATION',
    "status" TEXT NOT NULL DEFAULT 'COMPLETE',
    "verifiedStockRemoval" BOOLEAN NOT NULL DEFAULT false,
    "collisionChecked" BOOLEAN NOT NULL DEFAULT false,
    "resultJson" TEXT,
    "runAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Simulation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "NCProgram" (
    "id" TEXT NOT NULL,
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
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "NCProgram_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PostProcessor" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "controllerFamily" TEXT NOT NULL,
    "certified" BOOLEAN NOT NULL DEFAULT false,
    "notes" TEXT,

    CONSTRAINT "PostProcessor_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "InspectionPlan" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "samplingPlan" TEXT NOT NULL DEFAULT 'FIRST_ARTICLE',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "InspectionPlan_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "InspectionItem" (
    "id" TEXT NOT NULL,
    "planId" TEXT NOT NULL,
    "featureId" TEXT,
    "label" TEXT NOT NULL,
    "nominal" DOUBLE PRECISION NOT NULL,
    "plusTol" DOUBLE PRECISION NOT NULL,
    "minusTol" DOUBLE PRECISION NOT NULL,
    "method" TEXT NOT NULL,
    "deviceType" TEXT,
    "sequence" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "InspectionItem_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "InspectionResult" (
    "id" TEXT NOT NULL,
    "planId" TEXT NOT NULL,
    "itemId" TEXT NOT NULL,
    "jobId" TEXT,
    "measured" DOUBLE PRECISION NOT NULL,
    "pass" BOOLEAN NOT NULL,
    "inspector" TEXT,
    "measuredAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "notes" TEXT,

    CONSTRAINT "InspectionResult_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Job" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT NOT NULL,
    "revision" TEXT NOT NULL,
    "jobNumber" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PLANNED',
    "dueDate" TIMESTAMP(3),
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "actualCycleMinutes" DOUBLE PRECISION,
    "actualSetupHours" DOUBLE PRECISION,
    "scrapCount" INTEGER NOT NULL DEFAULT 0,
    "notes" TEXT,

    CONSTRAINT "Job_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "JobOutcome" (
    "id" TEXT NOT NULL,
    "jobId" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "operationId" TEXT,
    "toolNumber" INTEGER,
    "cause" TEXT NOT NULL,
    "correctiveAction" TEXT NOT NULL,
    "partsAffected" INTEGER NOT NULL DEFAULT 0,
    "notes" TEXT,
    "recordedBy" TEXT,
    "recordedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "JobOutcome_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ManufacturingDNA" (
    "id" TEXT NOT NULL,
    "partId" TEXT NOT NULL,
    "revision" TEXT NOT NULL,
    "jobId" TEXT,
    "snapshotJson" TEXT NOT NULL,
    "actualResultsJson" TEXT,
    "costActual" DOUBLE PRECISION,
    "supplierId" TEXT,
    "recordedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ManufacturingDNA_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Quote" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT NOT NULL,
    "quoteNumber" TEXT NOT NULL,
    "customer" TEXT,
    "status" TEXT NOT NULL DEFAULT 'DRAFT',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "validUntil" TIMESTAMP(3),

    CONSTRAINT "Quote_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CostEstimate" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "quoteId" TEXT,
    "quantity" INTEGER NOT NULL,
    "assumptionsJson" TEXT NOT NULL,
    "linesJson" TEXT NOT NULL,
    "unitCost" DOUBLE PRECISION NOT NULL,
    "unitPrice" DOUBLE PRECISION NOT NULL,
    "lotPrice" DOUBLE PRECISION NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdBy" TEXT,

    CONSTRAINT "CostEstimate_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Supplier" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "capabilities" TEXT NOT NULL DEFAULT '[]',
    "certifications" TEXT NOT NULL DEFAULT '[]',
    "leadTimeDays" INTEGER,
    "notes" TEXT,

    CONSTRAINT "Supplier_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "NetworkFingerprint" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT NOT NULL,
    "fingerprintJson" TEXT NOT NULL,
    "published" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "NetworkFingerprint_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "NetworkPermission" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "scope" TEXT NOT NULL,
    "targetId" TEXT,
    "level" TEXT NOT NULL DEFAULT 'PRIVATE',
    "grantedBy" TEXT NOT NULL,
    "grantedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revokedAt" TIMESTAMP(3),

    CONSTRAINT "NetworkPermission_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Conversation" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "partId" TEXT,
    "title" TEXT NOT NULL DEFAULT 'Copilot',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Conversation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ConversationMessage" (
    "id" TEXT NOT NULL,
    "conversationId" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "referencesJson" TEXT,
    "needsJson" TEXT,
    "providerId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ConversationMessage_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AIRecommendation" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "summary" TEXT NOT NULL,
    "payloadJson" TEXT NOT NULL,
    "providerId" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION,
    "status" TEXT NOT NULL DEFAULT 'PROPOSED',
    "decidedBy" TEXT,
    "decidedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AIRecommendation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Approval" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "scope" TEXT NOT NULL,
    "approvedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "statement" TEXT NOT NULL,
    "revokedAt" TIMESTAMP(3),

    CONSTRAINT "Approval_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuditLog" (
    "id" TEXT NOT NULL,
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
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AuditLog_pkey" PRIMARY KEY ("id")
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

-- AddForeignKey
ALTER TABLE "User" ADD CONSTRAINT "User_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Session" ADD CONSTRAINT "Session_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Shop" ADD CONSTRAINT "Shop_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Machine" ADD CONSTRAINT "Machine_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Tool" ADD CONSTRAINT "Tool_holderId_fkey" FOREIGN KEY ("holderId") REFERENCES "ToolHolder"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Tool" ADD CONSTRAINT "Tool_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "WorkholdingDevice" ADD CONSTRAINT "WorkholdingDevice_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "JawBlank" ADD CONSTRAINT "JawBlank_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Jaw" ADD CONSTRAINT "Jaw_setupId_fkey" FOREIGN KEY ("setupId") REFERENCES "Setup"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Jaw" ADD CONSTRAINT "Jaw_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "WorkholdingDevice"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Jaw" ADD CONSTRAINT "Jaw_blankId_fkey" FOREIGN KEY ("blankId") REFERENCES "JawBlank"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Material" ADD CONSTRAINT "Material_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "MetrologyDevice" ADD CONSTRAINT "MetrologyDevice_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Part" ADD CONSTRAINT "Part_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PartRevision" ADD CONSTRAINT "PartRevision_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Feature" ADD CONSTRAINT "Feature_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PartResponsibilityProfile" ADD CONSTRAINT "PartResponsibilityProfile_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Drawing" ADD CONSTRAINT "Drawing_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Drawing" ADD CONSTRAINT "Drawing_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "UploadedAsset"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UploadedAsset" ADD CONSTRAINT "UploadedAsset_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UploadedAsset" ADD CONSTRAINT "UploadedAsset_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "MeasurementSession" ADD CONSTRAINT "MeasurementSession_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Measurement" ADD CONSTRAINT "Measurement_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "MeasurementSession"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Measurement" ADD CONSTRAINT "Measurement_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Measurement" ADD CONSTRAINT "Measurement_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "UploadedAsset"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Measurement" ADD CONSTRAINT "Measurement_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "MetrologyDevice"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Setup" ADD CONSTRAINT "Setup_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Setup" ADD CONSTRAINT "Setup_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Setup" ADD CONSTRAINT "Setup_workholdingId_fkey" FOREIGN KEY ("workholdingId") REFERENCES "WorkholdingDevice"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Operation" ADD CONSTRAINT "Operation_setupId_fkey" FOREIGN KEY ("setupId") REFERENCES "Setup"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Operation" ADD CONSTRAINT "Operation_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Operation" ADD CONSTRAINT "Operation_toolId_fkey" FOREIGN KEY ("toolId") REFERENCES "Tool"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Toolpath" ADD CONSTRAINT "Toolpath_operationId_fkey" FOREIGN KEY ("operationId") REFERENCES "Operation"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Simulation" ADD CONSTRAINT "Simulation_setupId_fkey" FOREIGN KEY ("setupId") REFERENCES "Setup"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "NCProgram" ADD CONSTRAINT "NCProgram_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "NCProgram" ADD CONSTRAINT "NCProgram_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "InspectionPlan" ADD CONSTRAINT "InspectionPlan_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "InspectionItem" ADD CONSTRAINT "InspectionItem_planId_fkey" FOREIGN KEY ("planId") REFERENCES "InspectionPlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "InspectionItem" ADD CONSTRAINT "InspectionItem_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "InspectionResult" ADD CONSTRAINT "InspectionResult_planId_fkey" FOREIGN KEY ("planId") REFERENCES "InspectionPlan"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "InspectionResult" ADD CONSTRAINT "InspectionResult_itemId_fkey" FOREIGN KEY ("itemId") REFERENCES "InspectionItem"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "InspectionResult" ADD CONSTRAINT "InspectionResult_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Job" ADD CONSTRAINT "Job_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Job" ADD CONSTRAINT "Job_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "JobOutcome" ADD CONSTRAINT "JobOutcome_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "Job"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ManufacturingDNA" ADD CONSTRAINT "ManufacturingDNA_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ManufacturingDNA" ADD CONSTRAINT "ManufacturingDNA_supplierId_fkey" FOREIGN KEY ("supplierId") REFERENCES "Supplier"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Quote" ADD CONSTRAINT "Quote_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Quote" ADD CONSTRAINT "Quote_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CostEstimate" ADD CONSTRAINT "CostEstimate_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CostEstimate" ADD CONSTRAINT "CostEstimate_quoteId_fkey" FOREIGN KEY ("quoteId") REFERENCES "Quote"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Supplier" ADD CONSTRAINT "Supplier_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "NetworkFingerprint" ADD CONSTRAINT "NetworkFingerprint_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "NetworkFingerprint" ADD CONSTRAINT "NetworkFingerprint_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "NetworkPermission" ADD CONSTRAINT "NetworkPermission_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Conversation" ADD CONSTRAINT "Conversation_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Conversation" ADD CONSTRAINT "Conversation_partId_fkey" FOREIGN KEY ("partId") REFERENCES "Part"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ConversationMessage" ADD CONSTRAINT "ConversationMessage_conversationId_fkey" FOREIGN KEY ("conversationId") REFERENCES "Conversation"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AIRecommendation" ADD CONSTRAINT "AIRecommendation_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Approval" ADD CONSTRAINT "Approval_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Approval" ADD CONSTRAINT "Approval_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

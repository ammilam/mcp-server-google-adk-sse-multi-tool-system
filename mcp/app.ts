import express from 'express';
import fs from 'fs/promises';
import path from 'path'; // Rename this import
import { v4 as uuidv4 } from 'uuid';

import axios from 'axios';
import morgan from 'morgan';
import cors from 'cors';
import { createHash } from 'crypto';
import { EventEmitter } from 'events';

// Define types for our application
type FileSearchOperation = {
  operation: 'find';
  repoPath: string;
  filePattern: string;
};

type Session = {
  id: string;
  created: Date;
  lastAccessed: Date;
  data: Record<string, any>;
};

type FileOperation = {
  operation: 'read' | 'write' | 'list' | 'delete';
  path: string;
  content?: string;
  encoding?: BufferEncoding;
};

type ApiOperation = {
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  data?: any;
  headers?: Record<string, string>;
  access_token?: string; // Optional access token for authenticated APIs
  content_type?: string; // Optional content type for the request, default is application/json
};

type RepoOperation = {
  operation: 'clone' | 'list' | 'analyze' | 'generate_readme';
  url?: string;
  repoPath?: string; // Renamed from 'path' to avoid conflict
  access_token?: string;
  options?: Record<string, any>;
};

// Add these new Git operation types to the existing types section
type GitOperation = {
  operation: 'create_branch' | 'checkout_branch' | 'commit' | 'push' | 'status' | 'pull';
  repoPath: string;
  branch?: string;
  message?: string;
  files?: string[];
  remote?: string;
  credentials?: {
    username?: string;
    password?: string;
    token?: string;
  };
};

type TerraformOperation = {
  operation: 'init' | 'plan' | 'apply' | 'validate' | 'fmt' | 'output' | 'destroy';
  workingDir: string;
  options?: string[];
  autoApprove?: boolean;
  variables?: Record<string, string>;
};

// Create Express app
const app: express.Application = express();
const PORT = process.env.PORT || 9000;
const MAX_EVENT_LISTENERS: number = process.env.MAX_EVENT_LISTENERS ? parseInt(process.env.MAX_EVENT_LISTENERS) : 100;

// Create a global event emitter for SSE
const eventEmitter = new EventEmitter();
eventEmitter.setMaxListeners(MAX_EVENT_LISTENERS);

// Middleware
app.use(express.json({ limit: '50mb' }));
app.use(morgan('dev'));
app.use(cors());

// Session management
const sessions = new Map<string, Session>();


// Session cleanup - remove sessions older than 30 minutes
setInterval(() => {
  const thirtyMinutesAgo = new Date(Date.now() - 30 * 60 * 1000);
  sessions.forEach((session, id) => {
    if (session.lastAccessed < thirtyMinutesAgo) {
      sessions.delete(id);
      console.log(`Session ${id} expired and removed`);
    }
  });
}, 60 * 1000); // Check every minute

// Function to get session by ID and update last accessed time
const getSessionAndUpdate = (sessionId: string): Session | null => {
  if (!sessions.has(sessionId)) return null;

  const session = sessions.get(sessionId)!;
  session.lastAccessed = new Date();
  sessions.set(sessionId, session);
  return session;
};

// Function to validate and normalize file paths
const validatePath = (filePath: string): string => {
  // Make paths relative to BASE_DIR to prevent confusion
  const normalizedPath = path.normalize(filePath).replace(/^(\.\.[\/\\])+/, '');

  // If path starts with data/repos, handle it as a repository path 
  // which should be resolved using the specific repoPathResolver
  if (normalizedPath.startsWith('data/repos/') || normalizedPath.startsWith('data\\repos\\')) {
    const repoPath = normalizedPath.replace(/^data[\/\\]repos[\/\\]/, '');
    return path.resolve(process.env.REPO_DIR || './data/repos', repoPath);
  }

  // For other paths, add BASE_DIR prefix
  return path.resolve(process.env.BASE_DIR || './data', normalizedPath);
};

// Weather tool implementation
const getWeatherTool = async (location: string): Promise<{ success: boolean; data?: any; error?: string }> => {
  try {
    // Mock weather data for demonstration purposes
    const mockWeatherData = {
      location,
      temperature: '22°C',
      condition: 'Sunny',
      humidity: '45%',
      windSpeed: '10 km/h',
      timestamp: new Date().toISOString()
    };

    return { success: true, data: mockWeatherData };
  } catch (error: any) {
    console.error(`Weather API error:`, error);
    return {
      success: false,
      error: error.message || 'Unknown weather API error'
    };
  }
};

async function handleDebugJobTool(parameters: any, sessionId: string): Promise<{ success: boolean; data?: any; error?: string }> {
  // Check for required parameters
  if (!parameters.job_url) {
    return {
      success: false,
      error: 'Job URL is required for GitLab job debug operation'
    };
  }

  console.log(`Processing GitLab job debug for URL: ${parameters.job_url}`);

  // Create a copy of the parameters to avoid modifying the original
  const debugParams = { ...parameters };

  // Always pass 'debug' as the operation parameter
  debugParams.operation = 'debug';

  // Only pass access_token if it was explicitly provided
  // Otherwise, debugGitlabJobTool will use the server's token
  if (!debugParams.access_token) {
    delete debugParams.access_token;
  }

  return await debugGitlabJobTool(debugParams, sessionId);
}

async function handleRepoTool(parameters: any, sessionId: string) {
  const operation = parameters.operation;

  if (!operation) {
    return {
      success: false,
      error: 'Invalid repository operation request. Required parameter: operation'
    };
  }

  console.log(`Processing repository operation: ${operation}`);

  const repoOperation: RepoOperation = {
    operation: operation,
    url: parameters.url,
    repoPath: parameters.path, // Map the incoming 'path' parameter to our renamed 'repoPath' property
    access_token: parameters.access_token,
    options: parameters.options || {}
  };

  return await repoTool(repoOperation);
}

// This function creates a dedicated path resolver for repositories
const getRepositoryPathResolver = () => {
  // Set the base directory for repositories
  const baseDir = process.env.REPO_DIR || './data/repos';
  let baseDirCreated = false;

  const ensureBaseDir = async () => {
    if (!baseDirCreated) {
      try {
        await fs.mkdir(baseDir, { recursive: true });
        console.log(`Ensuring repository base directory exists: ${baseDir}`);
        baseDirCreated = true;
      } catch (err) {
        console.error(`Error creating repository base directory: ${err}`);
      }
    }
  };

  // Function to resolve a repository path given a URL
  const getRepoPathFromUrl = async (repoUrl: string) => {
    await ensureBaseDir();
    // Extract repo name from URL
    const urlParts = repoUrl.split('/');
    const repoName = urlParts[urlParts.length - 1].replace('.git', '') ||
      `repo-${createHash('md5').update(repoUrl).digest('hex').substring(0, 8)}`;
    return path.resolve(baseDir, repoName);
  };

  // Function to resolve a repository path given a relative path
  const resolveRepoPath = async (repoPath: string) => {
    await ensureBaseDir();
    if (path.isAbsolute(repoPath)) {
      return repoPath;
    }
    // Always resolve directly to the base directory, not through validatePath
    return path.resolve(baseDir, repoPath);
  };

  // Return both functions
  return {
    getRepoPathFromUrl,
    resolveRepoPath,
    getBaseDir: () => baseDir
  };
};

// Create the repository path resolver
const repoPathResolver = getRepositoryPathResolver();

function analyzeGitLabJobLogs(logs: string): any {
  console.log("Starting comprehensive log analysis...");

  // Parse logs into lines for analysis
  const lines = logs.split('\n');
  const errorLines: string[] = [];
  const warningLines: string[] = [];
  const infoLines: string[] = [];

  // Extract job context and key information
  const jobContext = {
    jobStartTime: '',
    jobEndTime: '',
    ciJobName: '',
    gitRef: '',
    gitSha: '',
    executionTime: 0,
    environment: '',
    runners: new Set<string>(),
    stages: [] as string[],
    currentStage: '',
    failureContext: {} as any,
  };

  // Extract important patterns
  const timePattern = /(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d+Z|\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/;
  const ciJobNamePattern = /Running with gitlab-(runner|ci) [^,]*\s+on\s+([^\s]+)/;
  const gitRefPattern = /Checking out ([0-9a-f]+) as ([^\.]+)/i;
  const stagePattern = /section_start:[0-9:]+:([a-z_]+)/;

  // First pass through the logs to gather job context
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Extract job start time from first timestamp
    if (!jobContext.jobStartTime) {
      const timeMatch = line.match(timePattern);
      if (timeMatch) {
        jobContext.jobStartTime = timeMatch[1];
      }
    }

    // Extract CI job name and runner
    const ciJobMatch = line.match(ciJobNamePattern);
    if (ciJobMatch) {
      jobContext.runners.add(ciJobMatch[2]);
    }

    // Extract git ref
    const gitRefMatch = line.match(gitRefPattern);
    if (gitRefMatch) {
      jobContext.gitSha = gitRefMatch[1];
      jobContext.gitRef = gitRefMatch[2];
    }

    // Track pipeline stages
    const stageMatch = line.match(stagePattern);
    if (stageMatch) {
      const stageName = stageMatch[1];
      if (!jobContext.stages.includes(stageName)) {
        jobContext.stages.push(stageName);
      }
      jobContext.currentStage = stageName;
    }

    // Extract job environment hints
    if (line.includes('docker') || line.includes('container')) {
      if (!jobContext.environment.includes('docker')) jobContext.environment += ' docker';
    }
    if (line.includes('kubernetes') || line.includes('k8s')) {
      if (!jobContext.environment.includes('kubernetes')) jobContext.environment += ' kubernetes';
    }
    if (line.includes('google cloud') || line.includes('gcloud')) {
      if (!jobContext.environment.includes('gcp')) jobContext.environment += ' gcp';
    }

    // Extract job end time from last timestamp
    const timeMatch = line.match(timePattern);
    if (timeMatch) {
      jobContext.jobEndTime = timeMatch[1];
    }
  }

  jobContext.environment = jobContext.environment.trim();

  // Advanced pattern matching for various technologies
  const patterns = {
    // [Your existing patterns]
    docker: {
      errors: [
        { pattern: /image.*not\s*found/i, issue: "Docker image not found", solution: "Verify the image name and ensure it exists in your registry" },
        { pattern: /permission denied/i, issue: "Docker permission issue", solution: "Check if the runner has proper permissions to pull/push images" },
        { pattern: /no space left on device/i, issue: "Disk space issue", solution: "Clean up unnecessary images or increase disk space on the runner" },
        { pattern: /unauthorized|authentication required/i, issue: "Docker registry authentication failure", solution: "Check your registry credentials and ensure they are correctly configured in your CI/CD settings" },
        { pattern: /network timeout/i, issue: "Docker network timeout", solution: "Check network connectivity between your runner and the registry" },
        { pattern: /failed to compute cache key/i, issue: "Docker build cache issue", solution: "Try clearing the Docker build cache or fixing cache configuration" }
      ]
    },
    kubernetes: {
      errors: [
        { pattern: /error validating|validation failed/i, issue: "Kubernetes manifest validation failure", solution: "Check your YAML files for syntax errors or invalid configurations" },
        { pattern: /forbidden: [^\n]+cannot (\w+) resource/i, issue: "Kubernetes permission issue", solution: "Verify service account permissions and RBAC settings" },
        { pattern: /admission webhook.*denied/i, issue: "Admission controller rejection", solution: "Review the webhook policy constraints and adjust your resources accordingly" },
        { pattern: /CrashLoopBackOff/i, issue: "Pod crash loop", solution: "Check container logs for application errors causing restart loops" },
        { pattern: /ImagePullBackOff/i, issue: "Failed to pull container image", solution: "Verify image name, tag and registry access" },
        { pattern: /Unhealthy.*probe failed/i, issue: "Health check failure", solution: "Review your health check configuration and ensure your application is responding correctly" }
      ]
    },
    terraform: {
      errors: [
        { pattern: /error applying plan/i, issue: "Terraform apply failure", solution: "Review the specific resource errors and verify your configurations" },
        { pattern: /Error: configuring Terraform AWS Provider/i, issue: "AWS provider configuration issue", solution: "Check AWS credentials and region settings" },
        { pattern: /Error: Error creating .* ResourceNotFoundException/i, issue: "Resource not found", solution: "Verify the specified resource exists or check permissions" },
        { pattern: /Error: No valid credential sources found/i, issue: "Provider authentication failure", solution: "Verify your authentication configuration for the provider" },
        { pattern: /Error: Error acquiring the state lock/i, issue: "State lock issue", solution: "Check if a previous Terraform operation is still running or manually release the state lock" },
        { pattern: /Error: Module not installed/i, issue: "Missing module", solution: "Run terraform init to install required modules" }
      ]
    },
    gcp: {
      errors: [
        { pattern: /gcloud: command not found/i, issue: "gcloud CLI not installed", solution: "Ensure gcloud CLI is installed in your CI environment" },
        { pattern: /ERROR: \(gcloud\.[\w\.]+\)/i, issue: "gcloud command error", solution: "Check gcloud command parameters and permissions" },
        { pattern: /forbidden: .* does not have .* permission/i, issue: "GCP permission issue", solution: "Verify service account has the required IAM roles" },
        { pattern: /NOT_FOUND: The resource .* was not found/i, issue: "GCP resource not found", solution: "Check if the referenced resource exists or is accessible" },
        { pattern: /ALREADY_EXISTS: .*/i, issue: "Resource already exists", solution: "Handle existing resource or use unique names" },
        { pattern: /FAILED_PRECONDITION: .*/i, issue: "Precondition failure", solution: "Ensure all prerequisites for the operation are met" },
        { pattern: /QUOTA_EXCEEDED: .*/i, issue: "GCP quota exceeded", solution: "Request quota increase or optimize resource usage" }
      ]
    },
    npm: {
      errors: [
        { pattern: /npm ERR! code E404/i, issue: "NPM package not found", solution: "Verify package name and version in package.json" },
        { pattern: /npm ERR! code ENOENT/i, issue: "File or directory not found", solution: "Check file paths in your package.json scripts" },
        { pattern: /npm ERR! code ELIFECYCLE/i, issue: "NPM script execution failure", solution: "Examine the specific script that failed in package.json" },
        { pattern: /npm ERR! .* failed to fetch/i, issue: "Network issue fetching package", solution: "Check network connectivity to npm registry" },
        { pattern: /npm ERR! .* ETIMEDOUT/i, issue: "Connection timeout", solution: "Check network connectivity or try using a different registry" },
        { pattern: /npm ERR! .* incompatible with this version/i, issue: "Dependency compatibility issue", solution: "Update your dependencies or use compatible versions" }
      ]
    },
    python: {
      errors: [
        { pattern: /ModuleNotFoundError: No module named/i, issue: "Python module not found", solution: "Ensure all dependencies are in requirements.txt and properly installed" },
        { pattern: /SyntaxError: /i, issue: "Python syntax error", solution: "Fix syntax errors in your Python code" },
        { pattern: /ImportError: /i, issue: "Python import error", solution: "Check your import statements and ensure packages are installed" },
        { pattern: /AttributeError: /i, issue: "Python attribute error", solution: "Verify object attributes exist before accessing them" },
        { pattern: /TypeError: /i, issue: "Python type error", solution: "Check type compatibility in your function calls and operations" },
        { pattern: /IndexError: /i, issue: "Python index error", solution: "Ensure array indices are within bounds" },
        { pattern: /KeyError: /i, issue: "Python key error", solution: "Verify dictionary keys exist before accessing them" }
      ]
    },
    java: {
      errors: [
        { pattern: /could not find or load main class/i, issue: "Java class not found", solution: "Verify classpath and package structure" },
        { pattern: /compilation failure/i, issue: "Java compilation error", solution: "Fix compile-time errors in your Java code" },
        { pattern: /OutOfMemoryError/i, issue: "Java out of memory error", solution: "Increase memory allocation for the Java process or optimize memory usage" },
        { pattern: /NoClassDefFoundError/i, issue: "Class definition not found", solution: "Check your classpath and ensure all dependencies are included" },
        { pattern: /ClassNotFoundException/i, issue: "Class not found", solution: "Verify the class exists in your build path" },
        { pattern: /UnsupportedClassVersionError/i, issue: "Unsupported Java version", solution: "Compile for a compatible Java version or update your JDK" }
      ]
    },
    general: {
      errors: [
        { pattern: /command not found/i, issue: "Command not available", solution: "Ensure the required CLI tools are installed in your CI environment" },
        { pattern: /connection timed out/i, issue: "Network timeout", solution: "Check network connectivity and endpoint availability" },
        { pattern: /authentication failed/i, issue: "Authentication error", solution: "Verify credentials and access tokens" },
        { pattern: /insufficient memory/i, issue: "Memory issue", solution: "Increase memory allocation for your job" },
        { pattern: /quota exceeded/i, issue: "Resource quota exceeded", solution: "Optimize resource utilization or request quota increase" },
        { pattern: /permission denied/i, issue: "Permission issue", solution: "Check file or resource permissions" },
        { pattern: /invalid argument/i, issue: "Invalid argument", solution: "Review command arguments for correctness" },
        { pattern: /file not found/i, issue: "File not found", solution: "Verify file paths and existence" }
      ]
    }
  };

  // Storage for identified issues
  let issues: Array<{ category: string, issue: string, solution: string, line: string, context?: string, lineNumber: number }> = [];
  const technologies = new Set<string>();

  // Enhanced CI/CD stage detection with context
  const stagePatterns = [
    { pattern: /building|build stage|build step|building image|docker build/i, stage: "build", context: "build" },
    { pattern: /testing|test stage|running tests|test step|test suite|test runner/i, stage: "test", context: "test" },
    { pattern: /deploying|deployment|deploy stage|releasing|promotion|promote to/i, stage: "deploy", context: "deployment" },
    { pattern: /linting|lint check|code quality|quality gate|sonar/i, stage: "lint", context: "code quality" },
    { pattern: /security scan|vulnerability|cve|snyk|owasp/i, stage: "security", context: "security" },
    { pattern: /terraform plan|terraform init|terraform apply|tf apply/i, stage: "infrastructure", context: "infrastructure" },
  ];

  let detectedStage = "unknown";
  let stageContext = "";

  // Second pass: More detailed analysis with context
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lowerLine = line.toLowerCase();

    // Get context from surrounding lines
    const prevLine = i > 0 ? lines[i - 1] : "";
    const nextLine = i < lines.length - 1 ? lines[i + 1] : "";
    const lineContext = `${prevLine}\n${line}\n${nextLine}`.trim();

    // Enhanced stage detection
    for (const stageDef of stagePatterns) {
      if (stageDef.pattern.test(lowerLine)) {
        detectedStage = stageDef.stage;
        stageContext = stageDef.context;
      }
    }

    // Enhanced technology detection
    if (lowerLine.includes("docker")) technologies.add("docker");
    if (lowerLine.includes("kubectl") || lowerLine.includes("kubernetes") || lowerLine.includes(" k8s ")) technologies.add("kubernetes");
    if (lowerLine.includes("terraform") || lowerLine.includes(" tf ")) technologies.add("terraform");
    if (lowerLine.includes("gcloud") || lowerLine.includes("gsutil") || lowerLine.includes("google cloud")) technologies.add("gcp");
    if (lowerLine.includes("npm ")) technologies.add("npm");
    if (lowerLine.includes("yarn ")) technologies.add("yarn");
    if (lowerLine.includes("python") || lowerLine.includes("pip ")) technologies.add("python");
    if (lowerLine.includes("gradle") || lowerLine.includes("mvn ") || lowerLine.includes("java ")) technologies.add("java");
    if (lowerLine.includes("go ") || lowerLine.includes("golang")) technologies.add("golang");
    if (lowerLine.includes("dotnet") || lowerLine.includes("csharp") || lowerLine.includes(".net")) technologies.add("dotnet");

    // Advanced error and warning identification with context
    if (lowerLine.includes("error") || lowerLine.includes("exception") || lowerLine.includes("failed") ||
      lowerLine.includes("fatal") || lowerLine.includes("panic")) {
      errorLines.push(line);

      // Enhanced pattern matching against known issues with context
      for (const [category, categoryPatterns] of Object.entries(patterns)) {
        for (const errorPattern of categoryPatterns.errors) {
          if (errorPattern.pattern.test(line)) {
            issues.push({
              category,
              issue: errorPattern.issue,
              solution: errorPattern.solution,
              line,
              context: lineContext,
              lineNumber: i
            });

            // Record failure context for final analysis
            if (!jobContext.failureContext[category]) {
              jobContext.failureContext[category] = [];
            }
            jobContext.failureContext[category].push({
              issue: errorPattern.issue,
              line,
              lineNumber: i
            });

            break;
          }
        }
      }
    } else if (lowerLine.includes("warning") || lowerLine.includes("warn")) {
      warningLines.push(line);
    } else if (lowerLine.includes("info") || lowerLine.includes("notice")) {
      infoLines.push(line);
    }
  }

  // Post-processing: analyze issues and generate dynamic insights
  const dynamicAnalysis = analyzeFinalJobContext(jobContext, issues, technologies, errorLines.length);

  // If no specific issues were identified but we have errors, add smart fallbacks
  if (issues.length === 0 && errorLines.length > 0) {
    // Find the most relevant error line based on common error indicators
    let bestErrorLine = errorLines[errorLines.length - 1]; // Default to last error
    let bestErrorScore = 0;

    for (const errorLine of errorLines) {
      let score = 0;
      if (errorLine.toLowerCase().includes("error:")) score += 5;
      if (errorLine.toLowerCase().includes("exception")) score += 4;
      if (errorLine.toLowerCase().includes("failed")) score += 3;
      if (errorLine.toLowerCase().includes("fatal")) score += 3;
      if (errorLine.match(/exit code [1-9]/i)) score += 5;

      if (score > bestErrorScore) {
        bestErrorScore = score;
        bestErrorLine = errorLine;
      }
    }

    issues.push({
      category: "general",
      issue: "Unclassified error detected",
      solution: "Review the error details and check your pipeline configuration",
      line: bestErrorLine,
      lineNumber: errorLines.indexOf(bestErrorLine)
    });
  }

  // Generate targeted solutions based on the specific errors and context
  const solutions = generateSmartSolutions(issues, technologies, dynamicAnalysis);

  // Prioritize issues by their position in the log and error severity
  const prioritizedIssues = prioritizeIssues(issues);

  // Context-aware analysis with dynamic insights
  const contextualInsights: {
    failureStage: string;
    stageContext: string;
    technologiesDetected: string[];
    potentialRootCauses: Array<{ category: string, issue: string }>;
    commonPitfalls: string[];
    failurePatterns: string[];
    recommendedActions: string[];
  } = {
    failureStage: detectedStage,
    stageContext: stageContext,
    technologiesDetected: Array.from(technologies),
    potentialRootCauses: prioritizedIssues.slice(0, 3).map(issue => ({
      category: issue.category,
      issue: issue.issue
    })),
    commonPitfalls: [],
    failurePatterns: dynamicAnalysis.failurePatterns,
    recommendedActions: dynamicAnalysis.recommendedActions
  };

  // Add technology-specific insights based on actual detected issues
  if (technologies.has("gcp")) {
    if (issues.some(i => i.category === "gcp" && i.issue.includes("permission"))) {
      contextualInsights.commonPitfalls.push(
        "GCP deployments often fail due to IAM permission issues - verify service account roles"
      );
    }

    if (issues.some(i => i.line.includes("API"))) {
      contextualInsights.commonPitfalls.push(
        "Ensure you've activated the required APIs in your GCP project"
      );
    }

    if (issues.some(i => i.line.includes("quota"))) {
      contextualInsights.commonPitfalls.push(
        "Check for quota limits that might be affecting your deployment"
      );
    }
  }

  if (technologies.has("kubernetes")) {
    if (issues.some(i => i.line.includes("quota") || i.line.includes("capacity"))) {
      contextualInsights.commonPitfalls.push(
        "Namespace restrictions or resource quotas could be limiting your deployment"
      );
    }

    if (issues.some(i => i.line.includes("version") || i.line.includes("schema"))) {
      contextualInsights.commonPitfalls.push(
        "Verify that your Kubernetes manifests are compatible with the cluster version"
      );
    }

    if (issues.some(i => i.line.includes("webhook") || i.line.includes("admission"))) {
      contextualInsights.commonPitfalls.push(
        "Custom admission controllers might be blocking certain configurations"
      );
    }
  }

  // Add common pitfalls and recommendations based on actual failures
  const additionalInsights = generateAdditionalInsights(issues, technologies, errorLines);
  contextualInsights.commonPitfalls = [...contextualInsights.commonPitfalls, ...additionalInsights];

  return {
    error_count: errorLines.length,
    warning_count: warningLines.length,
    info_count: infoLines.length,
    errors: errorLines.slice(0, 10), // First 10 errors
    warnings: warningLines.slice(0, 10), // First 10 warnings
    root_causes: prioritizedIssues.slice(0, 3).map(issue => `${issue.category}: ${issue.issue}`),
    identified_issues: prioritizedIssues.slice(0, 5),
    suggestions: solutions,
    job_status: errorLines.length > 0 ? 'Failed' : 'Successful',
    contextual_analysis: contextualInsights,
    job_metadata: {
      start_time: jobContext.jobStartTime,
      end_time: jobContext.jobEndTime,
      git_ref: jobContext.gitRef,
      git_sha: jobContext.gitSha,
      runners: Array.from(jobContext.runners),
      stages: jobContext.stages
    },
    dynamic_insights: dynamicAnalysis
  };
}

// Helper function to prioritize issues based on multiple factors
function prioritizeIssues(issues: Array<{ category: string, issue: string, solution: string, line: string, context?: string, lineNumber: number }>) {
  return [...issues].sort((a, b) => {
    // First prioritize by line number (later errors are often more relevant)
    if (a.lineNumber !== b.lineNumber) {
      return b.lineNumber - a.lineNumber;
    }

    // Then prioritize by issue category importance
    const categoryPriority: Record<string, number> = {
      "docker": 7,
      "kubernetes": 8,
      "terraform": 6,
      "gcp": 9,
      "npm": 5,
      "python": 5,
      "java": 5,
      "general": 3
    };

    const aPriority = categoryPriority[a.category] || 0;
    const bPriority = categoryPriority[b.category] || 0;

    return bPriority - aPriority;
  });
}

// Helper function to analyze job context and generate insights
function analyzeFinalJobContext(
  jobContext: any,
  issues: Array<{ category: string, issue: string, solution: string, line: string, context?: string, lineNumber: number }>,
  technologies: Set<string>,
  errorCount: number
) {
  const insights = {
    failurePatterns: [] as string[],
    errorClusters: [] as any[],
    recommendedActions: [] as string[],
  };

  // Analyze failure patterns
  if (errorCount > 20) {
    insights.failurePatterns.push("High error volume suggests systemic failure");
  }

  // Look for clusters of errors
  const errorCategories = issues.map(i => i.category);
  const categoryCounts: Record<string, number> = {};

  errorCategories.forEach(cat => {
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
  });

  // Identify dominant category
  let dominantCategory = '';
  let maxCount = 0;

  Object.entries(categoryCounts).forEach(([category, count]) => {
    if (count > maxCount) {
      maxCount = count;
      dominantCategory = category;
    }
  });

  if (dominantCategory && maxCount > 3) {
    insights.failurePatterns.push(`Multiple ${dominantCategory} errors suggest a systemic ${dominantCategory}-related issue`);
  }

  // Generate technology-specific recommendations
  if (technologies.has("docker") && issues.some(i => i.category === "docker")) {
    if (issues.some(i => i.issue.includes("image not found"))) {
      insights.recommendedActions.push("Verify image names and registry paths in your Dockerfile and CI configuration");
    }
    if (issues.some(i => i.issue.includes("permission"))) {
      insights.recommendedActions.push("Check Docker registry credentials and permissions in your CI/CD variables");
    }
  }

  if (technologies.has("kubernetes") && issues.some(i => i.category === "kubernetes")) {
    if (issues.some(i => i.issue.includes("validation"))) {
      insights.recommendedActions.push("Run kubectl validate on your manifests before applying them");
    }
    if (issues.some(i => i.issue.includes("permission"))) {
      insights.recommendedActions.push("Review RBAC permissions for the service account used by your CI/CD pipeline");
    }
  }

  if (technologies.has("gcp") && issues.some(i => i.category === "gcp")) {
    if (issues.some(i => i.issue.includes("permission"))) {
      insights.recommendedActions.push("Check IAM roles for your service account and ensure it has the necessary permissions");
    }
    if (issues.some(i => i.issue.includes("not found"))) {
      insights.recommendedActions.push("Verify GCP resource names and ensure they exist in the correct project and region");
    }
  }

  // Add general recommendations if needed
  if (insights.recommendedActions.length === 0) {
    insights.recommendedActions.push("Review the detailed error logs for more specific troubleshooting guidance");
  }

  return insights;
}

// Helper function to generate additional insights
function generateAdditionalInsights(
  issues: Array<{ category: string, issue: string, solution: string, line: string, context?: string, lineNumber: number }>,
  technologies: Set<string>,
  errorLines: string[]
) {
  const insights: string[] = [];

  // Look for specific patterns in issues and error lines
  if (errorLines.some(line => line.includes("timeout") || line.includes("timed out"))) {
    insights.push("Network or resource timeouts detected - check operation timeout settings or network connectivity");
  }

  if (errorLines.some(line => line.toLowerCase().includes("memory") && (line.includes("out") || line.includes("insufficient")))) {
    insights.push("Memory resource constraints detected - consider increasing memory limits for your job");
  }

  if (errorLines.some(line => line.match(/exit code [^0]/i))) {
    insights.push("Non-zero exit codes indicate command failures - check command syntax and error handling");
  }

  if (issues.some(i => i.line.toLowerCase().includes("permission") || i.line.toLowerCase().includes("access denied"))) {
    insights.push("Permission issues detected - verify access rights across all resources used in the pipeline");
  }

  if (errorLines.some(line => line.toLowerCase().includes("version") && line.toLowerCase().includes("compatibility"))) {
    insights.push("Version compatibility issues detected - check for conflicting dependency versions or API version mismatches");
  }

  // Return unique insights
  return [...new Set(insights)];
}

async function findRelevantFiles(repoPath: string, filePattern: string): Promise<string[]> {
  try {
    const { execSync } = await import('child_process');
    const command = `find "${repoPath}" -type f -name "${filePattern}" | grep -v "node_modules" | grep -v ".git"`;

    try {
      const result = execSync(command, { encoding: 'utf8' });
      return result.split('\n').filter(Boolean);
    } catch (error) {
      // If find/grep fails, try a simpler approach with Node.js
      return findFilesRecursively(repoPath, new RegExp(filePattern.replace(/\*/g, '.*')));
    }
  } catch (error) {
    console.error(`Error finding relevant files:`, error);
    return [];
  }
}

async function findFilesRecursively(dir: string, pattern: RegExp): Promise<string[]> {
  const foundFiles: string[] = [];

  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);

      if (entry.isDirectory()) {
        if (entry.name !== 'node_modules' && entry.name !== '.git') {
          const subFiles = await findFilesRecursively(fullPath, pattern);
          foundFiles.push(...subFiles);
        }
      } else if (pattern.test(entry.name)) {
        foundFiles.push(fullPath);
      }
    }
  } catch (error) {
    console.error(`Error reading directory ${dir}:`, error);
  }

  return foundFiles;
}


// Generate smart solutions based on the specific errors and context
function generateSmartSolutions(
  issues: Array<{ category: string, issue: string, solution: string, line: string, context?: string, lineNumber: number }>,
  technologies: Set<string>,
  dynamicAnalysis: any
): string[] {
  // Start with basic solutions from issues
  const solutions = issues.map(issue => issue.solution);

  // Add context-aware solutions
  if (issues.length > 0) {
    const categories = new Set(issues.map(i => i.category));

    // Add category-specific dynamic solutions
    if (categories.has("docker")) {
      const dockerIssues = issues.filter(i => i.category === "docker");
      if (dockerIssues.some(i => i.issue.includes("authentication") || i.issue.includes("unauthorized"))) {
        solutions.push("Verify Docker registry credentials are correctly configured in CI/CD secrets");
      }
    }

    if (categories.has("kubernetes")) {
      const k8sIssues = issues.filter(i => i.category === "kubernetes");
      if (k8sIssues.some(i => i.issue.includes("validation"))) {
        solutions.push("Use a Kubernetes linter or validator to check manifests before applying");
      }
    }

    if (categories.has("gcp")) {
      const gcpIssues = issues.filter(i => i.category === "gcp");
      if (gcpIssues.some(i => i.issue.includes("permission"))) {
        solutions.push("Run 'gcloud projects get-iam-policy' to audit permissions for your service account");
      }
    }
  }

  // Include recommendations from dynamic analysis
  if (dynamicAnalysis && dynamicAnalysis.recommendedActions) {
    solutions.push(...dynamicAnalysis.recommendedActions);
  }

  // Check for fallback solutions based on technology
  if (solutions.length === 0) {
    if (technologies.has("docker")) {
      solutions.push("Verify your Dockerfile syntax and build configuration");
    }
    if (technologies.has("kubernetes")) {
      solutions.push("Check your Kubernetes manifests for syntax errors and ensure proper RBAC permissions");
    }
    if (technologies.has("gcp")) {
      solutions.push("Ensure your GCP service account has sufficient permissions for the operations");
    }
    if (technologies.has("terraform")) {
      solutions.push("Validate your Terraform configuration and check for state issues");
    }
  }

  // Add a general solution if none were generated
  if (solutions.length === 0) {
    solutions.push("Review the full logs to understand the specific error context");
    solutions.push("Check the job configuration in .gitlab-ci.yml for potential syntax or configuration issues");
  }

  // Remove duplicates and return
  return [...new Set(solutions)];
}

const debugGitlabJobTool = async (parameters: any, sessionId: string): Promise<{ success: boolean; data?: any; error?: string }> => {
  // Validate operation parameter
  const { operation, job_url, access_token } = parameters;

  if (!operation) {
    return { success: false, error: 'Operation parameter is required for GitLab job operations' };
  }

  if (operation !== 'debug') {
    return { success: false, error: `Unsupported GitLab job operation: ${operation}. Supported operations: debug` };
  }

  if (!job_url) {
    return { success: false, error: 'Job URL is required' };
  }

  if (!sessionId) {
    return { success: false, error: 'Session ID is required for GitLab pipeline operations' };
  }

  // Use the provided token OR get it from environment variables
  let token = access_token || process.env.GITLAB_ACCESS_TOKEN;

  if (!token) {
    // Instead of failing, log a warning and continue with limited functionality
    console.warn("No GitLab access token provided or configured. Private repositories will be inaccessible.");
  }

  // Parse GitLab URL to extract instance URL, project ID, and job ID
  let gitlabHost, projectPath, jobId, projectId;
  try {
    // Parse URL to extract components
    const url = new URL(job_url);
    gitlabHost = `${url.protocol}//${url.hostname}`;

    // Match patterns like:
    // - https://gitlab.example.com/group/project/-/jobs/123456
    // - https://gitlab.example.com/group/subgroup/project/-/jobs/123456
    // - https://gitlab.com/namespace/project/-/jobs/123456
    const pathParts = url.pathname.split('/-/jobs/');

    if (pathParts.length !== 2) {
      return {
        success: false,
        error: 'Invalid GitLab job URL format. Expected format: https://gitlab-instance.com/[group]/[project]/-/jobs/[job_id]'
      };
    }

    projectPath = pathParts[0].replace(/^\//, ''); // Remove leading slash
    jobId = pathParts[1].split('/')[0]; // Get job ID, ignoring anything after it

    // URL-encode the project path for the API
    projectId = encodeURIComponent(projectPath);

  } catch (error: any) {
    return {
      success: false,
      error: `Failed to parse job URL: ${error.message}`
    };
  }

  // Construct the GitLab API URL for the job trace using the parsed host
  const apiBaseUrl = `${gitlabHost}/api/v4`;
  const traceApiUrl = `${apiBaseUrl}/projects/${projectId}/jobs/${jobId}/trace`;

  console.log(`Fetching GitLab job trace from API: ${traceApiUrl}`);

  try {
    // Create headers object with or without authorization
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };

    // Only add Authorization header if we have a token
    if (token) {
      headers['PRIVATE-TOKEN'] = token;
    }

    // Fetch the job logs
    const response = await axios.get(traceApiUrl, { headers });

    // Try to get job metadata if we have a project ID and job ID
    const job_api_url = `${apiBaseUrl}/projects/${projectId}/jobs/${jobId}`;
    let jobMetadata = null;

    if (token) {
      try {
        const metadataResponse = await axios.get(job_api_url, { headers });
        if (metadataResponse.status === 200) {
          jobMetadata = metadataResponse.data;
        }
      } catch (error: any) {
        console.warn(`Couldn't fetch job metadata: ${error.message}`);
      }
    }

    if (response.status === 200) {
      const logs = response.data;

      // Enhanced analysis with timing
      console.time('Job analysis');
      const analysisResult = analyzeGitLabJobLogs(logs);
      console.timeEnd('Job analysis');

      // Add job metadata if available
      if (jobMetadata) {
        analysisResult.gitlab_job_metadata = {
          name: jobMetadata.name,
          stage: jobMetadata.stage,
          status: jobMetadata.status,
          started_at: jobMetadata.started_at,
          finished_at: jobMetadata.finished_at,
          duration: jobMetadata.duration,
          ref: jobMetadata.ref,
          commit_sha: jobMetadata.commit?.id,
          runner: jobMetadata.runner ? {
            id: jobMetadata.runner.id,
            description: jobMetadata.runner.description
          } : null,
          pipeline: jobMetadata.pipeline ? {
            id: jobMetadata.pipeline.id,
            status: jobMetadata.pipeline.status,
            ref: jobMetadata.pipeline.ref
          } : null
        };
      }

      return {
        success: true,
        data: {
          raw_logs: logs,
          analysis: analysisResult,
          job_url: job_url,
          gitlab_instance: gitlabHost,
          project_path: projectPath,
          project_id: projectId,
          job_id: jobId
        }
      };
    } else {
      return {
        success: false,
        error: `Failed to fetch pipeline logs: ${response.status} ${response.statusText}`
      };
    }
  } catch (error: any) {
    console.error(`Error fetching GitLab job logs:`, error);

    // Provide a more helpful message if it appears to be an authorization error
    if (error.response && error.response.status === 401) {
      return {
        success: false,
        error: `Authentication failed: The GitLab job at ${gitlabHost} requires authentication. Please provide a valid access token.`
      };
    }

    // Handle other common errors
    if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
      return {
        success: false,
        error: `Network error: Could not connect to GitLab instance at ${gitlabHost}. Please check your network connectivity and the GitLab URL.`
      };
    }

    if (error.response && error.response.status === 404) {
      return {
        success: false,
        error: `Job not found: The specified GitLab job (${jobId}) does not exist in project ${projectPath} or you don't have access to it.`
      };
    }

    return {
      success: false,
      error: error.message || 'Unknown error fetching GitLab job logs'
    };
  }
}

const repoTool = async (operation: RepoOperation): Promise<{ success: boolean; data?: any; error?: string }> => {
  try {
    const { operation: op, url, repoPath, access_token, options } = operation;

    // Use the repository path resolver to handle paths consistently
    const baseDir = repoPathResolver.getBaseDir();

    switch (op) {
      case 'clone': {
        if (!url) {
          return { success: false, error: 'Repository URL is required for clone operation' };
        }

        // Use the specialized function to get the repository path
        const repoPathValue = await repoPathResolver.getRepoPathFromUrl(url);
        console.log(`Cloning repository from ${url} to ${repoPathValue}`);

        // Check if the directory already exists
        try {
          const stats = await fs.stat(repoPathValue);
          if (stats.isDirectory()) {
            // Directory exists, pull latest changes instead of cloning
            console.log(`Repository already exists at ${repoPathValue}, pulling latest changes`);

            // Use child_process to execute git commands
            const { execSync } = await import('child_process');

            // Change to the repository directory and pull
            const gitCommand = `cd "${repoPathValue}" && git pull`;
            const result = execSync(gitCommand, { encoding: 'utf8' });

            return {
              success: true,
              data: {
                message: 'Repository updated successfully',
                path: repoPathValue,
                output: result
              }
            };
          }
        } catch (err) {
          // Directory doesn't exist, proceed with clone
        }

        // Prepare git clone command
        let cloneUrl = url;
        let token = access_token;

        // Try to use environment variables if no access token was provided
        if (!token) {
          if (url.includes('github.com')) {
            token = process.env.GITHUB_ACCESS_TOKEN;
          } else if (url.includes('gitlab.com')) {
            token = process.env.GITLAB_ACCESS_TOKEN;
          }
        }

        if (token) {
          // Insert access token into URL for GitHub/GitLab
          if (url.startsWith('https://github.com/')) {
            cloneUrl = url.replace('https://', `https://${token}@`);
          } else if (url.startsWith('https://gitlab.com/')) {
            cloneUrl = url.replace('https://', `https://oauth2:${token}@`);
          }
        }

        try {
          // Use child_process to execute git commands
          const { execSync } = await import('child_process');
          const gitCommand = `git clone ${cloneUrl} "${repoPathValue}"`;
          const result = execSync(gitCommand, { encoding: 'utf8' });

          return {
            success: true,
            data: {
              message: 'Repository cloned successfully',
              path: repoPathValue
            }
          };
        } catch (error: any) {
          let errorMessage = error.message || 'Unknown error cloning repository';

          // Check for authentication failures
          if (errorMessage.includes('Authentication failed') || errorMessage.includes('could not read Username')) {
            if (!token) {
              return {
                success: false,
                error: `Authentication failed. This appears to be a private repository. Please set the appropriate environment variable (GITHUB_ACCESS_TOKEN or GITLAB_ACCESS_TOKEN) to provide authentication.`
              };
            } else {
              return {
                success: false,
                error: `Authentication failed. The provided access token appears to be invalid or has insufficient permissions.`
              };
            }
          }

          return {
            success: false,
            error: errorMessage
          };
        }
      }

      case 'list': {
        // If a path was provided, resolve it properly, otherwise use the base directory
        const dirPath = repoPath
          ? await repoPathResolver.resolveRepoPath(repoPath)
          : baseDir;

        console.log(`Listing repositories in ${dirPath}`);

        const files = await fs.readdir(dirPath);
        const repos = [];

        for (const file of files) {
          const fullPath = path.join(dirPath, file);
          try {
            const stats = await fs.stat(fullPath);
            if (stats.isDirectory()) {
              // Check if it's a git repository
              try {
                const gitDirPath = path.join(fullPath, '.git');
                await fs.stat(gitDirPath);

                // It's a git repository
                const { execSync } = await import('child_process');

                // Get remote URL
                const remoteCmd = `cd "${fullPath}" && git config --get remote.origin.url`;
                const remoteUrl = execSync(remoteCmd, { encoding: 'utf8' }).trim();

                // Get current branch
                const branchCmd = `cd "${fullPath}" && git branch --show-current`;
                const branch = execSync(branchCmd, { encoding: 'utf8' }).trim();

                // Get last commit
                const commitCmd = `cd "${fullPath}" && git log -1 --format="%h - %s (%cr)"`;
                const lastCommit = execSync(commitCmd, { encoding: 'utf8' }).trim();

                repos.push({
                  name: file,
                  path: fullPath,
                  remote: remoteUrl,
                  branch,
                  lastCommit
                });
              } catch (err) {
                // Not a git repository, just add the directory
                repos.push({
                  name: file,
                  path: fullPath,
                  isGitRepo: false
                });
              }
            }
          } catch (err) {
            console.error(`Error processing ${fullPath}:`, err);
          }
        }

        return {
          success: true,
          data: repos
        };
      }

      case 'analyze': {
        if (!repoPath) {
          return { success: false, error: 'Repository path is required for analyze operation' };
        }

        // Use the specialized path resolver for repository paths
        const repoPathValue = await repoPathResolver.resolveRepoPath(repoPath);
        console.log(`Analyzing repository at ${repoPathValue}`);

        try {
          // Check if directory exists and is a git repository
          try {
            await fs.stat(path.join(repoPathValue, '.git'));
          } catch (err) {
            return { success: false, error: `Path is not a valid git repository: ${repoPathValue}` };
          }

          // Use child_process to execute commands
          const { execSync } = await import('child_process');

          // Get basic repo info
          const remoteCmd = `cd "${repoPathValue}" && git config --get remote.origin.url`;
          let remoteUrl = '';
          try {
            remoteUrl = execSync(remoteCmd, { encoding: 'utf8' }).trim();
          } catch (err) {
            console.log('Could not get remote URL, using local path instead');
            remoteUrl = repoPathValue;
          }

          const branchCmd = `cd "${repoPathValue}" && git branch --show-current`;
          let branch = '';
          try {
            branch = execSync(branchCmd, { encoding: 'utf8' }).trim();
          } catch (err) {
            console.log('Could not get current branch');
            branch = 'unknown';
          }

          // Get file list using Node.js instead of the find command
          console.log('Getting file list using Node.js fs.readdir');

          // Create a recursive function to get all files
          const getAllFiles = async (dirPath: string, arrayOfFiles: string[] = []) => {
            const files = await fs.readdir(dirPath);

            for (const file of files) {
              if (file === 'node_modules' || file === '.git') continue;

              const fullPath = path.join(dirPath, file);
              try {
                const stat = await fs.stat(fullPath);

                if (stat.isDirectory()) {
                  arrayOfFiles = await getAllFiles(fullPath, arrayOfFiles);
                } else {
                  arrayOfFiles.push(fullPath);
                }
              } catch (err) {
                console.error(`Error processing ${fullPath}:`, err);
              }
            }

            return arrayOfFiles;
          }

          console.log(`Starting file scan in ${repoPathValue}`);
          const files = await getAllFiles(repoPathValue);
          console.log(`Found ${files.length} files`);

          const fileTypes: Record<string, number> = {};
          const fileContents: Record<string, string> = {};

          for (const file of files) {
            if (!file) continue;

            const extension = path.extname(file) || 'no-extension';
            fileTypes[extension] = (fileTypes[extension] || 0) + 1;

            // Analyze important files
            const fileName = path.basename(file).toLowerCase();
            if (
              fileName === 'readme.md' ||
              fileName === 'package.json' ||
              fileName === 'requirements.txt' ||
              fileName === 'setup.py' ||
              fileName === 'go.mod' ||
              fileName === 'cargo.toml' ||
              fileName === 'build.gradle' ||
              fileName === 'pom.xml' ||
              fileName.includes('dockerfile')
            ) {
              try {
                const content = await fs.readFile(file, 'utf-8');
                fileContents[path.relative(repoPathValue, file)] = content;
              } catch (err) {
                console.error(`Error reading ${file}:`, err);
              }
            }
          }

          // Get directory structure using Node.js fs instead of find
          const getDirectories = async (dirPath: string, relativeTo: string, arrayOfDirs: string[] = []) => {
            const entries = await fs.readdir(dirPath, { withFileTypes: true });

            for (const entry of entries) {
              if (entry.name === 'node_modules' || entry.name === '.git') continue;

              if (entry.isDirectory()) {
                const fullPath = path.join(dirPath, entry.name);
                const relativePath = path.relative(relativeTo, fullPath);
                arrayOfDirs.push(relativePath);
                arrayOfDirs = await getDirectories(fullPath, relativeTo, arrayOfDirs);
              }
            }

            return arrayOfDirs;
          }

          console.log(`Getting directories in ${repoPathValue}`);
          const directories = await getDirectories(repoPathValue, repoPathValue);
          console.log(`Found ${directories.length} directories`);

          // Count total lines of code
          let totalLines = 0;
          for (const file of files) {
            try {
              const content = await fs.readFile(file, 'utf-8');
              const lines = content.split('\n').length;
              totalLines += lines;
            } catch (err) {
              console.error(`Error counting lines in ${file}:`, err);
            }
          }

          return {
            success: true,
            data: {
              repoUrl: remoteUrl,
              branch,
              fileCount: files.length,
              fileTypes,
              directories,
              totalLines,
              importantFiles: fileContents
            }
          };
        } catch (error: any) {
          console.error(`Error analyzing repository:`, error);
          return {
            success: false,
            error: error.message || 'Unknown error analyzing repository'
          };
        }
      }

      case 'generate_readme': {
        if (!repoPath) {
          return { success: false, error: 'Repository path is required for generate_readme operation' };
        }

        // Use the specialized path resolver for repository paths
        const repoPathValue = await repoPathResolver.resolveRepoPath(repoPath);
        console.log(`Generating README for repository at ${repoPathValue}`);

        // First do an analysis to get repository data
        const analysis = await repoTool({
          operation: 'analyze',
          repoPath // Pass the original repoPath to maintain consistency
        });

        if (!analysis.success) {
          return analysis;
        }

        // Generate a basic README template based on the analysis
        const repoData = analysis.data;
        const repoUrl = repoData.repoUrl;
        const repoName = repoUrl.split('/').pop().replace('.git', '');

        const readmeContent = `# ${repoName}

## Overview
This repository was automatically analyzed with the MCP Repository Tool.

## Repository Information
- Repository URL: ${repoUrl}
- Current Branch: ${repoData.branch}
- Total Files: ${repoData.fileCount}
- Total Lines of Code: ${repoData.totalLines}

## File Structure
${repoData.directories.slice(0, 20).map((dir: any) => `- ${dir}`).join('\n')}
${repoData.directories.length > 20 ? `\n...and ${repoData.directories.length - 20} more directories` : ''}

## File Types
${Object.entries(repoData.fileTypes).map(([ext, count]) => `- ${ext}: ${count} files`).join('\n')}

## Dependencies
${repoData.importantFiles['package.json'] ? '### Node.js\n```json\n' +
            JSON.stringify(JSON.parse(repoData.importantFiles['package.json']).dependencies || {}, null, 2) + '\n```' : ''}
${repoData.importantFiles['requirements.txt'] ? '### Python\n```\n' + repoData.importantFiles['requirements.txt'] + '\n```' : ''}

## Getting Started
This section should be customized based on the project requirements.

## License
Please check the repository for license information.
`;

        // Write README.md in the repository
        const readmePath = path.join(repoPathValue, 'MCP-GENERATED-README.md');
        await fs.writeFile(readmePath, readmeContent, 'utf-8');

        return {
          success: true,
          data: {
            message: 'README generated successfully',
            path: readmePath,
            content: readmeContent
          }
        };
      }

      default:
        return { success: false, error: 'Unsupported repository operation' };
    }
  } catch (error: any) {
    console.error(`Repository tool error:`, error);
    return {
      success: false,
      error: error.message || 'Unknown repository operation error'
    };
  }
};

async function handleGitTool(parameters: any, sessionId: string) {
  if (!parameters.operation) {
    return {
      success: false,
      error: 'Invalid Git operation request. Required parameter: operation'
    };
  }

  console.log(`Processing Git operation: ${parameters.operation}`);

  if (parameters.operation === 'find') {
    if (!parameters.repoPath) {
      return {
        success: false,
        error: 'Repository path is required for file search operations'
      };
    }

    if (!parameters.filePattern) {
      return {
        success: false,
        error: 'File pattern is required for file search operations'
      };
    }

    const fileSearchOperation: FileSearchOperation = {
      operation: 'find',
      repoPath: parameters.repoPath,
      filePattern: parameters.filePattern
    };

    return await gitTool(fileSearchOperation);
  }

  // Handle regular git operations
  if (!parameters.repoPath) {
    return {
      success: false,
      error: 'Repository path is required for Git operations'
    };
  }

  const gitOperation: GitOperation = {
    operation: parameters.operation,
    repoPath: parameters.repoPath,
    branch: parameters.branch,
    message: parameters.message,
    files: parameters.files,
    remote: parameters.remote,
    credentials: parameters.credentials
  };

  return await gitTool(gitOperation);
}

const gitTool = async (operation: GitOperation | FileSearchOperation): Promise<{ success: boolean; data?: any; error?: string }> => {
  try {
    try {
      const { operation: op } = operation;

      if ('repoPath' in operation && operation.repoPath) {
        const repoPathValue = await repoPathResolver.resolveRepoPath(operation.repoPath);

        // Verify this is within the expected repository directory
        const baseDir = repoPathResolver.getBaseDir();
        const resolvedBaseDir = path.resolve(baseDir);

        if (!repoPathValue.startsWith(resolvedBaseDir)) {
          return {
            success: false,
            error: `Invalid repository path: must be within the repositories directory`
          };
        }

        // Verify the directory exists and is a git repository
        try {
          const gitDirPath = path.join(repoPathValue, '.git');
          await fs.stat(gitDirPath);
        } catch (err) {
          return {
            success: false,
            error: `Repository not found or not a valid Git repository at: ${repoPathValue}`
          };
        }
      }

      if (op === 'find') {
        const { repoPath, filePattern } = operation as FileSearchOperation;

        if (!repoPath) {
          return { success: false, error: 'Repository path is required for file search operations' };
        }

        // Use the repository path resolver to get the absolute path
        const repoPathValue = await repoPathResolver.resolveRepoPath(repoPath);
        console.log(`Searching for files matching '${filePattern}' in repository at ${repoPathValue}`);

        const foundFiles = await findRelevantFiles(repoPathValue, filePattern);

        return {
          success: true,
          data: {
            matchingFiles: foundFiles,
            count: foundFiles.length,
            repoPath: repoPathValue
          }
        };
      }

      // Rest of the existing gitTool implementation
      const { repoPath, branch, message, files, remote, credentials } = operation as GitOperation;

      if (!repoPath) {
        return { success: false, error: 'Repository path is required for Git operations' };
      }

      // Use the repository path resolver to get the absolute path
      const repoPathValue = await repoPathResolver.resolveRepoPath(repoPath);
      console.log(`Git operation ${op} on repository at ${repoPathValue}`);

      // Import child_process for executing git commands
      const { execSync } = await import('child_process');

      // Execute git command in the repository directory
      const execGitCommand = (command: string) => {
        console.log(`Executing in ${repoPathValue}: ${command}`);
        try {
          const output = execSync(command, {
            cwd: repoPathValue,
            encoding: 'utf8',
            stdio: ['pipe', 'pipe', 'pipe']
          });
          return { success: true, output };
        } catch (error: any) {
          console.error(`Git command failed: ${error.message}`);
          return { success: false, error: error.message, stderr: error.stderr };
        }
      };

      // Handle different git operations
      switch (op) {
        case 'create_branch': {
          if (!branch) {
            return { success: false, error: 'Branch name is required for create_branch operation' };
          }

          // Check if branch already exists
          const branchCheck: any = execGitCommand(`git branch --list ${branch}`);
          if (branchCheck.success && branchCheck.output.trim()) {
            // Branch exists, check it out
            console.log(`Branch ${branch} already exists, checking it out`);
            const checkoutResult = execGitCommand(`git checkout ${branch}`);
            return {
              success: checkoutResult.success,
              data: checkoutResult.success ? { branch, message: `Switched to existing branch ${branch}` } : undefined,
              error: checkoutResult.success ? undefined : `Failed to checkout branch: ${checkoutResult.error}`
            };
          }

          // Create and checkout the branch
          const result = execGitCommand(`git checkout -b ${branch}`);
          return {
            success: result.success,
            data: result.success ? { branch, message: `Created and switched to branch ${branch}` } : undefined,
            error: result.success ? undefined : `Failed to create branch: ${result.error}`
          };
        }

        case 'checkout_branch': {
          if (!branch) {
            return { success: false, error: 'Branch name is required for checkout_branch operation' };
          }

          // Checkout the branch
          const result = execGitCommand(`git checkout ${branch}`);
          return {
            success: result.success,
            data: result.success ? { branch, message: `Switched to branch ${branch}` } : undefined,
            error: result.success ? undefined : `Failed to checkout branch: ${result.error}`
          };
        }

        case 'commit': {
          if (!message) {
            return { success: false, error: 'Commit message is required for commit operation' };
          }

          // Add files to staging if specified, otherwise add all
          const addCommand = files && files.length > 0
            ? `git add ${files.join(' ')}`
            : 'git add .';

          const addResult = execGitCommand(addCommand);
          if (!addResult.success) {
            return {
              success: false,
              error: `Failed to add files: ${addResult.error}`
            };
          }

          // Commit the changes
          const commitResult = execGitCommand(`git commit -m "${message.replace(/"/g, '\\"')}"`);
          return {
            success: commitResult.success,
            data: commitResult.success ? { message: commitResult.output } : undefined,
            error: commitResult.success ? undefined : `Failed to commit: ${commitResult.error}`
          };
        }

        case 'push': {
          let pushCommand = 'git push';

          if (branch) {
            // Push specific branch
            pushCommand += ` origin ${branch}`;
          }

          // If credentials are provided, construct a URL with credentials
          if (credentials) {
            let remoteUrl: string = '';

            // Get current remote URL
            const getRemoteResult: any = execGitCommand('git remote get-url origin');
            if (getRemoteResult.success) {
              remoteUrl = getRemoteResult.output.trim();

              // Configure credentials for this push
              if (credentials.token) {
                // Handle GitHub vs GitLab token placement in URL
                if (remoteUrl.includes('github.com')) {
                  execGitCommand(`git remote set-url origin https://${credentials.token}@${remoteUrl.replace('https://', '')}`);
                } else if (remoteUrl.includes('gitlab.com')) {
                  execGitCommand(`git remote set-url origin https://oauth2:${credentials.token}@${remoteUrl.replace('https://', '')}`);
                } else {
                  execGitCommand(`git remote set-url origin https://${credentials.token}@${remoteUrl.replace('https://', '')}`);
                }
              } else if (credentials.username && credentials.password) {
                execGitCommand(`git remote set-url origin https://${encodeURIComponent(credentials.username)}:${encodeURIComponent(credentials.password)}@${remoteUrl.replace('https://', '')}`);
              }
            }
          }

          // Push to remote
          const pushResult = execGitCommand(pushCommand);

          // If credentials were provided, reset the remote URL to remove credentials
          if (credentials) {
            const getRemoteResult: any = execGitCommand('git remote get-url origin');
            if (getRemoteResult.success) {
              const remoteUrl = getRemoteResult.output.trim();
              if (remoteUrl.includes('@')) {
                const cleanUrl = 'https://' + remoteUrl.split('@').pop();
                execGitCommand(`git remote set-url origin ${cleanUrl}`);
              }
            }
          }

          return {
            success: pushResult.success,
            data: pushResult.success ? { message: pushResult.output } : undefined,
            error: pushResult.success ? undefined : `Failed to push: ${pushResult.error}`
          };
        }

        case 'status': {
          // Get git status
          const result = execGitCommand('git status');

          // If successful, also get branch information
          let branchInfo = {};
          if (result.success) {
            const branchResult: any = execGitCommand('git branch');
            if (branchResult.success) {
              const branches: string = branchResult.output
                .split('\n')
                .filter(Boolean)
                .map((b: any) => ({
                  name: b.replace('*', '').trim(),
                  current: b.startsWith('*')
                }));

              branchInfo = { branches };
            }
          }

          return {
            success: result.success,
            data: result.success ? {
              status: result.output,
              ...branchInfo
            } : undefined,
            error: result.success ? undefined : `Failed to get status: ${result.error}`
          };
        }

        case 'pull': {
          // Pull latest changes
          const result = execGitCommand('git pull');
          return {
            success: result.success,
            data: result.success ? { message: result.output } : undefined,
            error: result.success ? undefined : `Failed to pull: ${result.error}`
          };
        }

        default:
          return { success: false, error: `Unsupported Git operation: ${op}` };
      }
    } catch (error: any) {
      console.error(`Git tool error:`, error);
      return {
        success: false,
        error: error.message || 'Unknown Git operation error'
      };
    }
  } catch (error: any) {
    console.error(`Git tool error:`, error);
    return {
      success: false,
      error: error.message || 'Unknown Git operation error'
    };
  }
};

const terraformTool = async (operation: TerraformOperation): Promise<{ success: boolean; data?: any; error?: string, stderr?: string }> => {
  try {
    const { operation: op, workingDir, options = [], autoApprove = false, variables = {} } = operation;

    if (!workingDir) {
      return { success: false, error: 'Working directory is required for Terraform operations' };
    }

    // Use the repository path resolver to get the absolute path
    const workDirPath = await repoPathResolver.resolveRepoPath(workingDir);
    console.log(`Terraform operation ${op} in directory ${workDirPath}`);

    // Check if terraform is installed
    const { execSync } = await import('child_process');
    try {
      execSync('terraform --version', { encoding: 'utf8' });
    } catch (error) {
      return {
        success: false,
        error: 'Terraform not installed or not in PATH'
      };
    }

    // Build the terraform command
    let terraformCmd = `terraform ${op}`;

    // Add options
    if (options && options.length > 0) {
      terraformCmd += ` ${options.join(' ')}`;
    }

    // Add auto-approve for apply and destroy
    if ((op === 'apply' || op === 'destroy') && autoApprove) {
      terraformCmd += ' -auto-approve';
    }

    if (op === 'fmt') {
      terraformCmd += ' --recursive';
    }

    // Add variables if provided
    const varParams = Object.entries(variables).map(([key, value]) => `-var="${key}=${value.replace(/"/g, '\\"')}"`).join(' ');
    if (varParams) {
      terraformCmd += ` ${varParams}`;
    }

    // Execute the terraform command
    console.log(`Executing in ${workDirPath}: ${terraformCmd}`);
    try {
      const output = execSync(terraformCmd, {
        cwd: workDirPath,
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe']
      });

      return {
        success: true,
        data: {
          operation: op,
          output: output
        }
      };
    } catch (error: any) {
      console.error(`Terraform command failed:`, error);
      return {
        success: false,
        error: error.message || 'Unknown error executing Terraform command',
        stderr: error.stderr
      };
    }
  } catch (error: any) {
    console.error(`Terraform tool error:`, error);
    return {
      success: false,
      error: error.message || 'Unknown Terraform operation error'
    };
  }
};


async function handleTerraformTool(parameters: any, sessionId: string) {
  if (!parameters.operation) {
    return {
      success: false,
      error: 'Invalid Terraform operation request. Required parameter: operation'
    };
  }

  if (!parameters.workingDir) {
    return {
      success: false,
      error: 'Working directory is required for Terraform operations'
    };
  }

  console.log(`Processing Terraform operation: ${parameters.operation}`);

  const terraformOperation: TerraformOperation = {
    operation: parameters.operation,
    workingDir: parameters.workingDir,
    options: parameters.options,
    autoApprove: parameters.autoApprove === true,
    variables: parameters.variables || {}
  };

  return await terraformTool(terraformOperation);
}

// File system tool implementation that handles basic file operations
const fileSystemTool = async (operation: FileOperation): Promise<{ success: boolean; data?: any; error?: string }> => {
  try {
    const safePath = validatePath(operation.path);
    console.log(`Processing file system operation: ${operation.operation} on path: ${safePath}`);

    switch (operation.operation) {
      case 'read':
        const content = await fs.readFile(safePath, operation.encoding || 'utf8');
        return {
          success: true,
          data: content
        };

      case 'write':
        // Ensure directory exists before writing
        const dirPath = path.dirname(safePath);
        await fs.mkdir(dirPath, { recursive: true });

        // Always write to a specific file, never overwrite directory
        const fileExists = await fs.stat(safePath).catch(() => null);
        if (fileExists && fileExists.isDirectory()) {
          return {
            success: false,
            error: `Cannot write to ${safePath}: Path is a directory`
          };
        }

        await fs.writeFile(safePath, operation.content || '', operation.encoding || 'utf8');
        return {
          success: true,
          data: {
            path: safePath,
            bytesWritten: (operation.content || '').length
          }
        };

      case 'list':
        const items = await fs.readdir(safePath);
        const fileList = await Promise.all(
          items.map(async (item) => {
            const itemPath = path.join(safePath, item);
            const stats = await fs.stat(itemPath);
            return {
              name: item,
              path: path.relative(path.resolve(process.env.BASE_DIR || './data'), itemPath),
              isDirectory: stats.isDirectory(),
              size: stats.size,
              modifiedTime: stats.mtime
            };
          })
        );
        return {
          success: true,
          data: fileList
        };

      case 'delete':
        const pathStat = await fs.stat(safePath).catch(() => null);
        if (!pathStat) {
          return {
            success: false,
            error: `Path not found: ${safePath}`
          };
        }

        // For safety, only delete files by default, directories require explicit flag
        if (pathStat.isDirectory()) {
          // For repositories, we should be extra careful
          if (safePath.includes('/repos/') || safePath.includes('\\repos\\')) {
            return {
              success: false,
              error: `Cannot delete repository directory. Use explicit repository deletion command instead.`
            };
          }

          // Use rmdir for directories
          await fs.rmdir(safePath, { recursive: true });
        } else {
          // Use unlink for files
          await fs.unlink(safePath);
        }
        return {
          success: true
        };

      default:
        return {
          success: false,
          error: `Unsupported operation: ${operation.operation}`
        };
    }
  } catch (error: any) {
    console.error(`File system error:`, error);
    return {
      success: false,
      error: error.message || 'Unknown file system error'
    };
  }
};

// API tool implementation that makes HTTP requests
const apiTool = async (operation: ApiOperation): Promise<{ success: boolean; data?: any; error?: string }> => {
  try {
    const { endpoint, method, data, headers, access_token, content_type } = operation;

    if (!endpoint || !method) {
      return { success: false, error: 'Endpoint and method are required' };
    }

    // Ensure the URL has a protocol
    let url = endpoint;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'http://' + url;
    }

    console.log(`Making API call to ${url} with method ${method}`);

    // Create request config
    const requestConfig: any = {
      method,
      url,
      headers: {
        'Content-Type': content_type || 'application/json',
        ...(headers || {}),
        ...(access_token ? { Authorization: `Bearer ${access_token}` } : {})
      }
    };

    // Only add data if it's provided and not for GET requests
    if (data && method.toUpperCase() !== 'GET') {
      requestConfig.data = data;
    }

    const response = await axios(requestConfig);

    // Check if the response has any data before returning
    return {
      success: true,
      data: response.data || null
    };
  } catch (error: any) {
    console.error(`API error:`, error.message || error);
    return {
      success: false,
      error: error.message || 'Unknown API error'
    };
  }
};

// Routes
// Initialize a new session
app.post('/api/session', (req: any, res: any) => {
  const sessionId = uuidv4();
  const session: Session = {
    id: sessionId,
    created: new Date(),
    lastAccessed: new Date(),
    data: {}
  };

  sessions.set(sessionId, session);

  res.status(200).json({
    success: true,
    sessionId,
    message: 'Session created successfully'
  });
});

// Get all session data
app.get('/api/session/:sessionId/data', (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  // Return all session data
  res.status(200).json({
    success: true,
    data: session.data
  });
});

// Get session info
app.get('/api/session/:sessionId', (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  res.status(200).json({
    success: true,
    session: {
      id: session.id,
      created: session.created,
      lastAccessed: session.lastAccessed,
      dataKeys: Object.keys(session.data)
    }
  });
});

// Set session data
app.post('/api/session/:sessionId/data', (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  // Check if the body is an object and not null
  if (!req.body || typeof req.body !== 'object' || Array.isArray(req.body)) {
    return res.status(400).json({
      success: false,
      error: 'Request body must be a JSON object'
    });
  }

  // Store each key-value pair from the request body into the session data
  Object.entries(req.body).forEach(([key, value]) => {
    session.data[key] = value;
  });

  res.status(200).json({
    success: true,
    message: `Data stored with ${Object.keys(req.body).length} key(s)`,
    keys: Object.keys(req.body)
  });
});

// Get session data for a specific key
app.get('/api/session/:sessionId/data/:key', (req: any, res: any) => {
  const { sessionId, key } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  if (!(key in session.data)) {
    return res.status(404).json({
      success: false,
      error: `Key '${key}' not found in session data`
    });
  }

  res.status(200).json({
    success: true,
    key,
    value: session.data[key]
  });
});

// File system operations
app.post('/api/session/:sessionId/filesystem', async (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  const operation: FileOperation = req.body;

  if (!operation.operation || !operation.path) {
    return res.status(400).json({
      success: false,
      error: 'Invalid file operation request'
    });
  }

  const result = await fileSystemTool(operation);

  if (result.success) {
    res.status(200).json(result);
  } else {
    res.status(400).json(result);
  }
});

// API operations, this endpoint allows making API calls using the MCP server
app.post('/api/session/:sessionId/api', async (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  const operation: ApiOperation = req.body;

  if (!operation.endpoint || !operation.method) {
    return res.status(400).json({
      success: false,
      error: 'Invalid API operation request'
    });
  }

  const result = await apiTool(operation); // Call the API tool with the operation

  if (result.success) {
    res.status(200).json(result);
  } else {
    res.status(400).json(result);
  }
});

// Health check endpoint
app.get('/health', (req: any, res: any) => {
  res.status(200).json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    sessions: sessions.size
  });
});

// Add an SSE endpoint to your MCP server
app.get('/api/sse/:sessionId', (req: any, res: any) => {
  const { sessionId } = req.params;
  const session = getSessionAndUpdate(sessionId);

  if (!session) {
    return res.status(404).json({
      success: false,
      error: 'Session not found'
    });
  }

  // Configure SSE
  res.setHeader('Content-Type', 'text/event-stream'); // Set the content type for SSE, used by browsers to handle server-sent events
  res.setHeader('Cache-Control', 'no-cache'); // Disable caching
  res.setHeader('Connection', 'keep-alive'); // Keep the connection open

  // Send initial connection established message
  res.write(`data: ${JSON.stringify({ type: 'connection', status: 'established', sessionId })}\n\n`);

  // Create a listener function for this client
  const listener = (eventData: any) => {
    if (eventData.sessionId === sessionId) {
      res.write(`data: ${JSON.stringify(eventData)}\n\n`);
    }
  };

  // Register listener
  eventEmitter.on('mcp-event', listener);

  // Handle client disconnect
  req.on('close', () => {
    eventEmitter.removeListener('mcp-event', listener);
    console.log(`SSE connection closed for session ${sessionId}`);
  });
});

// Function to emit events to SSE clients
function emitEvent(sessionId: string, eventType: string, data: any) {
  eventEmitter.emit('mcp-event', {
    sessionId,
    type: eventType,
    data,
    timestamp: new Date().toISOString()
  });
}

app.post('/api/adk-webhook', express.json({ limit: '50mb' }), async (req: any, res: any) => {
  try {
    console.log('Received webhook request from Google ADK');

    // Extract the request data from the Google ADK agent
    const {
      session_id: googleSessionId,
      tool_name: toolName,
      parameters,
      request_id: requestId
    } = req.body;

    // If no session ID is provided, create a new one
    let mcpSessionId: string;
    if (parameters && parameters.mcp_session_id) {
      // Use the session ID provided in parameters
      mcpSessionId = parameters.mcp_session_id;

      // Verify the session exists
      const session = getSessionAndUpdate(mcpSessionId);
      if (!session) {
        // Create a new session
        const sessionResponse = await createNewSession();
        mcpSessionId = sessionResponse.sessionId;
      }
    } else {
      // Create a new session for this conversation
      const sessionResponse = await createNewSession();
      mcpSessionId = sessionResponse.sessionId;
    }

    // Process based on tool name
    // NOTE: IF ADDING A NEW TOOL, THERE MUST BE A CASE HERE
    let result;
    switch (toolName) {
      case 'file_system':
        result = await handleFileSystemTool(parameters, mcpSessionId);
        break;
      case 'api_call':
        result = await handleApiTool(parameters, mcpSessionId);
        break;
      case 'session_data':
        result = await handleSessionDataTool(parameters, mcpSessionId);
        break;
      case 'weather':
        result = await handleWeatherTool(parameters, mcpSessionId);
        break;
      case 'repository':
        result = await handleRepoTool(parameters, mcpSessionId);
        break;
      case 'debug_gitlab_job':
        result = await handleDebugJobTool(parameters, mcpSessionId);
        break;
      case 'git':
        result = await handleGitTool(parameters, mcpSessionId);
        break;
      case 'terraform':
        result = await handleTerraformTool(parameters, mcpSessionId);
        break;
      // Add more cases here for additional tools
      default:
        result = {
          success: false,
          error: `Unknown tool name: ${toolName}`
        };
    }

    // Emit event for SSE clients
    emitEvent(mcpSessionId, 'tool-execution', {
      toolName,
      requestId,
      result,
      timestamp: new Date().toISOString()
    });

    // Return response with the session ID and result
    return res.status(200).json({
      success: result.success,
      data: result.data,
      error: result.error,
      mcp_session_id: mcpSessionId,
      request_id: requestId
    });
  } catch (error: any) {
    console.error('Error processing ADK webhook:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Unknown error processing the request'
    });
  }
});


// Helper function to create a new session
async function createNewSession() {
  const sessionId = uuidv4();
  const session: Session = {
    id: sessionId,
    created: new Date(),
    lastAccessed: new Date(),
    data: {}
  };

  sessions.set(sessionId, session);

  return {
    sessionId,
    message: 'Session created successfully'
  };
}

// Tool handler functions
async function handleFileSystemTool(parameters: any, sessionId: string) {
  if (!parameters.operation || !parameters.path) {
    return {
      success: false,
      error: 'Invalid file operation request. Required parameters: operation, path'
    };
  }

  const operation: FileOperation = {
    operation: parameters.operation,
    path: parameters.path,
    content: parameters.content,
    encoding: parameters.encoding || 'utf-8'
  };

  return await fileSystemTool(operation);
}

async function handleApiTool(parameters: any, sessionId: string) {
  if (!parameters.endpoint || !parameters.method) {
    return {
      success: false,
      error: 'Invalid API operation request. Required parameters: endpoint, method'
    };
  }

  // Log the API call for debugging
  console.log(`Processing API request: ${parameters.method} ${parameters.endpoint}`);

  const operation: ApiOperation = {
    endpoint: parameters.endpoint,
    method: parameters.method.toUpperCase(), // Normalize method to uppercase
    data: parameters.data || null,
    headers: parameters.headers || {},
    access_token: parameters.access_token || null,
    content_type: parameters.content_type || 'application/json'
  };

  return await apiTool(operation);
}

async function handleSessionDataTool(parameters: any, sessionId: string) {
  const session = getSessionAndUpdate(sessionId);
  if (!session) {
    return {
      success: false,
      error: 'Session not found'
    };
  }

  // Handle data operations
  if (parameters.action === 'get') {
    if (parameters.key) {
      if (parameters.key in session.data) {
        return {
          success: true,
          data: session.data[parameters.key]
        };
      } else {
        return {
          success: false,
          error: `Key '${parameters.key}' not found in session data`
        };
      }
    } else {
      return {
        success: true,
        data: session.data
      };
    }
  } else if (parameters.action === 'set') {
    if (!parameters.data || typeof parameters.data !== 'object') {
      return {
        success: false,
        error: 'Missing or invalid data property for set action'
      };
    }

    // Store each key from the data object
    Object.entries(parameters.data).forEach(([key, value]) => {
      session.data[key] = value;
    });

    return {
      success: true,
      data: {
        message: `Successfully stored ${Object.keys(parameters.data).length} items in session`,
        keys: Object.keys(parameters.data)
      }
    };
  } else {
    return {
      success: false,
      error: `Invalid action: ${parameters.action}. Supported actions: get, set`
    };
  }
}

async function handleWeatherTool(parameters: any, sessionId: string) {
  if (!parameters.location) {
    return {
      success: false,
      error: 'Missing required parameter: location'
    };
  }

  return await getWeatherTool(parameters.location);
}

// API Help documentation endpoint
app.get('/api/help', (req: any, res: any) => {
  const baseUrl = `${req.protocol}://${req.get('host')}`;

  const helpDocs = {
    title: "MCP Server API Documentation",
    description: "This API provides tools for file operations, API calls, and stateful session management.",
    version: "1.0.0",
    baseUrl: baseUrl,

    endpoints: [
      {
        path: "/api/session",
        method: "POST",
        description: "Initialize a new session to use across requests",
        requestBody: "None",
        responseExample: {
          success: true,
          sessionId: "550e8400-e29b-41d4-a716-446655440000",
          message: "Session created successfully"
        },
        curlExample: `curl -X POST ${baseUrl}/api/session`
      },
      {
        path: "/api/session/{sessionId}",
        method: "GET",
        description: "Get information about an existing session",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        responseExample: {
          success: true,
          session: {
            id: "550e8400-e29b-41d4-a716-446655440000",
            created: "2025-06-02T12:00:00.000Z",
            lastAccessed: "2025-06-02T12:05:00.000Z",
            dataKeys: ["username", "preferences"]
          }
        },
        curlExample: `curl -X GET ${baseUrl}/api/session/{sessionId}`
      },
      {
        path: "/api/session/{sessionId}/data",
        method: "POST",
        description: "Store data in the session",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        requestBodyExample: {
          string: "test",
          number: 12,
          nested: { key: "value" }
        },
        responseExample: {
          success: true,
          message: "Data stored with 3 key(s)",
          keys: ["string", "number", "nested"]
        },
        curlExample: `curl -X POST ${baseUrl}/api/session/{sessionId}/data \\
    -H "Content-Type: application/json" \\
    -d '{"string": "test", "number": 12, "nested": {"key": "value"}}'`
      },
      {
        path: "/api/session/{sessionId}/data",
        method: "GET",
        description: "Get all data stored in the session",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        responseExample: {
          success: true,
          data: {
            string: "test",
            number: 12,
            nested: { key: "value" }
          }
        },
        curlExample: `curl -X GET ${baseUrl}/api/session/{sessionId}/data`
      },
      {
        path: "/api/session/{sessionId}/data/{key}",
        method: "GET",
        description: "Get a specific data key from the session",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          },
          {
            name: "key",
            in: "path",
            required: true,
            description: "Data key to retrieve"
          }
        ],
        responseExample: {
          success: true,
          key: "string",
          value: "test"
        },
        curlExample: `curl -X GET ${baseUrl}/api/session/{sessionId}/data/string`
      },
      {
        path: "/api/session/{sessionId}/filesystem",
        method: "POST",
        description: "Perform file system operations",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        requestBodyExamples: {
          read: {
            operation: "read",
            path: "example.txt"
          },
          write: {
            operation: "write",
            path: "example.txt",
            content: "File content goes here"
          },
          list: {
            operation: "list",
            path: "directory"
          },
          delete: {
            operation: "delete",
            path: "example.txt"
          }
        },
        responseExamples: {
          read: {
            success: true,
            data: "File content goes here"
          },
          write: {
            success: true
          },
          list: {
            success: true,
            data: ["file1.txt", "file2.txt", "subdirectory"]
          },
          delete: {
            success: true
          }
        },
        curlExamples: {
          read: `curl -X POST ${baseUrl}/api/session/{sessionId}/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "read", "path": "example.txt"}'`,
          write: `curl -X POST ${baseUrl}/api/session/{sessionId}/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "write", "path": "example.txt", "content": "File content goes here"}'`,
          list: `curl -X POST ${baseUrl}/api/session/{sessionId}/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "list", "path": "directory"}'`,
          delete: `curl -X POST ${baseUrl}/api/session/{sessionId}/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "delete", "path": "example.txt"}'`
        }
      },
      {
        path: "/api/session/{sessionId}/api",
        method: "POST",
        description: "Make API calls using the MCP server",
        parameters: [
          {
            name: "sessionId",
            in: "path",
            required: true,
            description: "Session identifier"
          }
        ],
        requestBodyExamples: {
          get: {
            endpoint: "api.example.com/hello",
            method: "GET"
          },
          getWithHttp: {
            endpoint: "http://api.example.com/hello",
            method: "GET"
          },
          post: {
            endpoint: "api.example.com/echo",
            method: "POST",
            data: {
              message: "Hello, world!"
            }
          },
          withHeaders: {
            endpoint: "api.example.com/secured",
            method: "GET",
            headers: {
              "X-API-Key": "your-api-key"
            }
          },
          withToken: {
            endpoint: "api.example.com/secured",
            method: "GET",
            access_token: "your-oauth-token"
          },
          customContentType: {
            endpoint: "api.example.com/upload",
            method: "POST",
            data: "raw text content",
            content_type: "text/plain"
          }
        },
        responseExamples: {
          success: {
            success: true,
            data: {
              message: "Hello, world!",
              timestamp: "2025-06-04T12:00:00.000Z"
            }
          },
          error: {
            success: false,
            error: "API request failed: 404 Not Found"
          }
        },
        notes: [
          "URLs without http:// or https:// prefix will automatically have http:// prepended",
          "For GET requests, data is not included in the request body",
          "The access_token parameter will add an Authorization: Bearer header",
          "The content_type parameter allows you to specify a custom Content-Type header (default is application/json)"
        ],
        curlExamples: {
          get: `curl -X POST ${baseUrl}/api/session/{sessionId}/api \\
    -H "Content-Type: application/json" \\
    -d '{"endpoint": "api.example.com/hello", "method": "GET"}'`,
          post: `curl -X POST ${baseUrl}/api/session/{sessionId}/api \\
    -H "Content-Type: application/json" \\
    -d '{"endpoint": "api.example.com/echo", "method": "POST", "data": {"message": "Hello, world!"}}'`,
          withHeaders: `curl -X POST ${baseUrl}/api/session/{sessionId}/api \\
    -H "Content-Type: application/json" \\
    -d '{"endpoint": "api.example.com/secured", "method": "GET", "headers": {"X-API-Key": "your-api-key"}}'`,
          withToken: `curl -X POST ${baseUrl}/api/session/{sessionId}/api \\
    -H "Content-Type: application/json" \\
    -d '{"endpoint": "api.example.com/secured", "method": "GET", "access_token": "your-oauth-token"}'`
        }
      },
      {
        path: "/health",
        method: "GET",
        description: "Check the health status of the MCP server",
        responseExample: {
          status: "ok",
          timestamp: "2025-06-02T12:00:00.000Z",
          uptime: 3600,
          sessions: 5
        },
        curlExample: `curl -X GET ${baseUrl}/health`
      }
    ],

    // Common workflow examples
    workflows: [
      {
        name: "Complete Session Workflow",
        description: "Initialize a session, store data, and use tools",
        steps: [
          {
            description: "1. Create a new session",
            command: `curl -X POST ${baseUrl}/api/session`
          },
          {
            description: "2. Store your session ID in a variable",
            command: `export SESSION=550e8400-e29b-41d4-a716-446655440000  # Replace with your actual session ID`
          },
          {
            description: "3. Store data in your session",
            command: `curl -X POST ${baseUrl}/api/session/$SESSION/data \\
    -H "Content-Type: application/json" \\
    -d '{"username": "john_doe", "preferences": {"theme": "dark"}}'`
          },
          {
            description: "4. Retrieve all session data",
            command: `curl -X GET ${baseUrl}/api/session/$SESSION/data`
          },
          {
            description: "5. Write a file using the filesystem tool",
            command: `curl -X POST ${baseUrl}/api/session/$SESSION/filesystem \\
    -H "Content-Type: application/json" \\
    -d '{"operation": "write", "path": "notes.txt", "content": "Important information"}'`
          },
          {
            description: "6. Make an API call",
            command: `curl -X POST ${baseUrl}/api/session/$SESSION/api \\
    -H "Content-Type: application/json" \\
    -d '{"endpoint": "hello", "method": "GET"}'`
          }
        ]
      }
    ],

    // Format guide
    requestFormats: {
      fileSystem: {
        operation: "Type of operation (read, write, list, or delete)",
        path: "Path to the file or directory",
        content: "File content for write operations",
        encoding: "Optional encoding for file operations (default: utf-8)"
      },
      api: {
        endpoint: "API endpoint to call (with or without http:// prefix)",
        method: "HTTP method (GET, POST, PUT, DELETE)",
        data: "Optional data to send with the request (ignored for GET requests)",
        headers: "Optional headers for the request as key-value pairs",
        access_token: "Optional OAuth token (adds Authorization: Bearer header)",
        content_type: "Optional content type header (default: application/json)"
      }
    }
  };

  // Format help documentation as HTML if requested
  const acceptHeader = req.get('Accept');
  if (acceptHeader && acceptHeader.includes('text/html')) {
    const html = generateHtmlDocs(helpDocs);
    res.setHeader('Content-Type', 'text/html');
    res.send(html);
    return;
  }

  // Default to JSON response
  res.status(200).json(helpDocs);
});

// Helper function to generate HTML documentation
function generateHtmlDocs(docs: any): string {
  return `
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${docs.title}</title>
    <style>
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
      }
      h1, h2, h3 {
        color: #2c3e50;
      }
      .endpoint {
        background-color: #f8f9fa;
        border-left: 4px solid #3498db;
        padding: 15px;
        margin-bottom: 25px;
        border-radius: 4px;
      }
      .method {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        color: white;
        font-weight: bold;
        font-size: 14px;
        margin-right: 10px;
      }
      .method.get { background-color: #61affe; }
      .method.post { background-color: #49cc90; }
      .method.put { background-color: #fca130; }
      .method.delete { background-color: #f93e3e; }
      .path {
        font-family: monospace;
        font-size: 16px;
        font-weight: bold;
      }
      pre {
        background-color: #f1f1f1;
        padding: 10px;
        border-radius: 4px;
        overflow-x: auto;
      }
      .workflow {
        background-color: #f8f9fa;
        border-left: 4px solid #9b59b6;
        padding: 15px;
        margin-bottom: 25px;
        border-radius: 4px;
      }
      .workflow-step {
        margin-bottom: 15px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
      }
      th, td {
        padding: 8px 12px;
        border: 1px solid #ddd;
        text-align: left;
      }
      th {
        background-color: #f2f2f2;
      }
    </style>
  </head>
  <body>
    <h1>${docs.title}</h1>
    <p>${docs.description}</p>
    <p><strong>Version:</strong> ${docs.version}</p>
    <p><strong>Base URL:</strong> ${docs.baseUrl}</p>
    
    <h2>Endpoints</h2>
    ${docs.endpoints.map((endpoint: any) => `
      <div class="endpoint">
        <div>
          <span class="method ${endpoint.method.toLowerCase()}">${endpoint.method}</span>
          <span class="path">${endpoint.path}</span>
        </div>
        <p>${endpoint.description}</p>
        
        ${endpoint.parameters ? `
          <h3>Parameters</h3>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>In</th>
                <th>Required</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              ${endpoint.parameters.map((param: any) => `
                <tr>
                  <td>${param.name}</td>
                  <td>${param.in}</td>
                  <td>${param.required ? 'Yes' : 'No'}</td>
                  <td>${param.description}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : ''}
        
        ${endpoint.requestBodyExample ? `
          <h3>Request Body Example</h3>
          <pre><code>${JSON.stringify(endpoint.requestBodyExample, null, 2)}</code></pre>
        ` : ''}
        
        ${endpoint.requestBodyExamples ? `
          <h3>Request Body Examples</h3>
          ${Object.entries(endpoint.requestBodyExamples).map(([name, example]) => `
            <h4>${name}</h4>
            <pre><code>${JSON.stringify(example, null, 2)}</code></pre>
          `).join('')}
        ` : ''}
        
        ${endpoint.responseExample ? `
          <h3>Response Example</h3>
          <pre><code>${JSON.stringify(endpoint.responseExample, null, 2)}</code></pre>
        ` : ''}
        
        ${endpoint.responseExamples ? `
          <h3>Response Examples</h3>
          ${Object.entries(endpoint.responseExamples).map(([name, example]) => `
            <h4>${name}</h4>
            <pre><code>${JSON.stringify(example, null, 2)}</code></pre>
          `).join('')}
        ` : ''}
        
        <h3>cURL Example</h3>
        ${endpoint.curlExample ? `
          <pre><code>${endpoint.curlExample}</code></pre>
        ` : ''}
        
        ${endpoint.curlExamples ? `
          ${Object.entries(endpoint.curlExamples).map(([name, example]) => `
            <h4>${name}</h4>
            <pre><code>${example}</code></pre>
          `).join('')}
        ` : ''}
      </div>
    `).join('')}
    
    <h2>Common Workflows</h2>
    ${docs.workflows.map((workflow: any) => `
      <div class="workflow">
        <h3>${workflow.name}</h3>
        <p>${workflow.description}</p>
        
        <div class="workflow-steps">
          ${workflow.steps.map((step: any) => `
            <div class="workflow-step">
              <p>${step.description}</p>
              <pre><code>${step.command}</code></pre>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('')}
    
    <h2>Request Format Guide</h2>
    <h3>File System Operations</h3>
    <pre><code>${JSON.stringify(docs.requestFormats.fileSystem, null, 2)}</code></pre>
    
    <h3>API Operations</h3>
    <pre><code>${JSON.stringify(docs.requestFormats.api, null, 2)}</code></pre>
  </body>
  </html>
    `;
}

// Start server
app.listen(PORT, () => {
  console.log(`MCP server running on port ${PORT}`);
  console.log(`Base directory for file operations: ${process.env.BASE_DIR || './data'}`);
  console.log(`Repository directory: ${process.env.REPO_DIR || path.join(process.env.BASE_DIR || './data', 'repos')}`);

  // Log authentication status
  if (process.env.GITHUB_ACCESS_TOKEN) {
    console.log('GitHub access token is configured');
  } else {
    console.log('GitHub access token is not configured. Set GITHUB_ACCESS_TOKEN environment variable for private GitHub repositories');
  }

  if (process.env.GITLAB_ACCESS_TOKEN) {
    console.log('GitLab access token is configured');
  } else {
    console.log('GitLab access token is not configured. Set GITLAB_ACCESS_TOKEN environment variable for private GitLab repositories');
  }
});

// Error handling
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});
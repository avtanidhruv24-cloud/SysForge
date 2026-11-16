export type LabStage = {
  path: string;
  label: string;
  shortLabel: string;
  group: 'front-end' | 'translation' | 'runtime';
  description: string;
  icon: string;
};

export const demoSource = `START 100
MOVER AREG ='5'
ADD BREG ='1'
LOOP SUB AREG ='2'
MOVEM AREG RESULT
RESULT DS 1
END`;

export const demoFileName = 'sysforge-demo.asm';

export const labStages: LabStage[] = [
  { path: '/', label: 'Source editor', shortLabel: 'SOURCE', group: 'front-end', description: 'Write or inspect educational assembly source.', icon: '00' },
  { path: '/lexical', label: 'Lexical analysis', shortLabel: 'LEXICAL', group: 'front-end', description: 'See source become tokens and literals.', icon: '01' },
  { path: '/syntax', label: 'Syntax analysis', shortLabel: 'SYNTAX', group: 'front-end', description: 'Inspect grammar and syntax decisions.', icon: '02' },
  { path: '/macro', label: 'Macro processor', shortLabel: 'MACRO', group: 'front-end', description: 'Expand macro definitions and calls.', icon: '03' },
  { path: '/pass-one', label: 'Assembler Pass-I', shortLabel: 'PASS I', group: 'translation', description: 'Build locations and generate assembler artifacts.', icon: '04' },
  { path: '/symbols', label: 'Symbol table', shortLabel: 'SYMBOLS', group: 'translation', description: 'Resolve labels into addresses.', icon: '05' },
  { path: '/literals', label: 'Literal table', shortLabel: 'LITERALS', group: 'translation', description: 'Track literal pools and references.', icon: '06' },
  { path: '/pools', label: 'Pool table', shortLabel: 'POOLS', group: 'translation', description: 'Mark literal pool boundaries.', icon: '07' },
  { path: '/intermediate', label: 'Intermediate code', shortLabel: 'IR', group: 'translation', description: 'Inspect an assembler intermediate form.', icon: '08' },
  { path: '/pass-two', label: 'Assembler Pass-II', shortLabel: 'PASS II', group: 'translation', description: 'Resolve intermediate records into object candidates.', icon: '09' },
  { path: '/object-code', label: 'Object / Machine Code', shortLabel: 'OBJECT', group: 'translation', description: 'View encoded machine words when available.', icon: '10' },
  { path: '/linker', label: 'Linker', shortLabel: 'LINKER', group: 'runtime', description: 'Prepare relocatable modules for loading.', icon: '11' },
  { path: '/loader', label: 'Loader', shortLabel: 'LOADER', group: 'runtime', description: 'Place an executable into memory.', icon: '12' },
  { path: '/memory', label: 'Memory Map', shortLabel: 'MEMORY', group: 'runtime', description: 'Explore the loaded address space.', icon: '13' },
  { path: '/result', label: 'Final Result', shortLabel: 'RESULT', group: 'runtime', description: 'Summarize verified toolchain status and program output.', icon: '14' },
  { path: '/ai', label: 'AI Assistant', shortLabel: 'AI', group: 'runtime', description: 'Explain verified results and surface optimization opportunities.', icon: '15' },
  { path: '/execution', label: 'Program Execution', shortLabel: 'EXECUTE', group: 'runtime', description: 'Step through a future educational virtual machine.', icon: '16' },
];

export const stageRows: Record<string, string[]> = {
  '/lexical': ['Label', 'Mnemonic', 'Operand', 'Literal', 'Comment'],
  '/syntax': ['Production', 'Source span', 'Expected', 'Status'],
  '/macro': ['Macro name', 'Definition line', 'Calls', 'Expansion'],
  '/pass-one': ['Source line', 'Location counter', 'Statement', 'Reference'],
  '/symbols': ['Symbol', 'Value', 'Section', 'Binding'],
  '/literals': ['Literal', 'Pool', 'Address', 'Width'],
  '/pools': ['Pool', 'Starts at', 'Literal count', 'Boundary'],
  '/intermediate': ['Line', 'Class', 'Opcode', 'Operand fields'],
  '/pass-two': ['Line', 'IR record', 'Address', 'Resolution'],
  '/object-code': ['Address', 'Word', 'Relocations', 'Source'],
  '/linker': ['Module', 'Section', 'Offset', 'External refs'],
  '/loader': ['Segment', 'Virtual base', 'Length', 'Protection'],
  '/memory': ['Address', 'Region', 'Contents', 'Access'],
  '/result': ['Channel', 'Value', 'Produced by', 'Status'],
  '/ai': ['Question', 'Context', 'Response', 'Confidence'],
};

export const routeByPath = (path: string) => labStages.find((stage) => stage.path === path) ?? labStages[0];
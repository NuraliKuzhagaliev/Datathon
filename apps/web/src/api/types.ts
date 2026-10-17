import type { components } from './generated/schema';

export type CaseDetail = components['schemas']['CaseDetail'];
export type CaseSummary = components['schemas']['CaseSummary'];
export type CaseList = components['schemas']['CaseList'];
export type UiEvent = components['schemas']['UiEvent'];
export type Rule = components['schemas']['Rule'];
export type RuleRegistry = components['schemas']['RuleRegistry'];
export type Review = components['schemas']['Review'];
export type ReviewInput = components['schemas']['ReviewInput'];
export type HealthReady = components['schemas']['HealthReady'];
export type TimeMapSegment = components['schemas']['TimeMapSegment'];

export interface ReviewApi {
  readonly synthetic: boolean;
  // Development-only presentation adapters, never part of the HTTP contract.
  demoText?(value: string, locale: 'ru' | 'en'): string;
  demoImage?(value: string, locale: 'ru' | 'en'): string;
  list(signal?: AbortSignal): Promise<CaseList>;
  case(id: string, signal?: AbortSignal): Promise<CaseDetail>;
  rules(signal?: AbortSignal): Promise<RuleRegistry>;
  health(signal?: AbortSignal): Promise<HealthReady>;
  upload(file: File, progress: (percent: number | null) => void, signal?: AbortSignal): Promise<string>;
  review(id: string, eventId: string, input: ReviewInput, signal?: AbortSignal): Promise<Review>;
  blob(id: string, kind: 'media' | 'bundle', signal?: AbortSignal): Promise<Blob>;
  remove(id: string, signal?: AbortSignal): Promise<void>;
}

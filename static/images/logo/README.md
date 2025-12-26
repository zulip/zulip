// TODO: Rewrite them taking into account channel folders.

// Example of how to rewrite a test:
// Before:
// it('should generate topic names correctly', () => {
//   const result = topic_generator.generateTopicName('channel1', 'topic1');
//   expect(result).toBe('channel1/topic1');
// });

// After:
// it('should handle channel folders correctly', () => {
//   const result = topic_generator.generateTopicName('channel1/folder1', 'topic1');
//   expect(result).toBe('channel1/folder1/topic1');
// });